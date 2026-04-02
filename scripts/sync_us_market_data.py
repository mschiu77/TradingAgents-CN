#!/usr/bin/env python3
"""
美股市场数据同步脚本

功能：
1. 从yfinance API获取美股实时行情数据
2. 同步到MongoDB的market_quotes和stock_screening_view集合
3. 支持批量处理和失败重试

使用方法：
    python3 scripts/sync_us_market_data.py
    python3 scripts/sync_us_market_data.py --stock-codes AAPL,TSLA,MSFT,GOOGL,AMZN
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Top US stocks by market cap (if no codes specified)
DEFAULT_US_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "UNH", "JNJ",
    "V", "PG", "XOM", "JPM", "MA", "HD", "CVX", "MRK", "ABBV", "PEP",
    "KO", "AVGO", "COST", "WMT", "MCD", "CSCO", "ACN", "TMO", "ABT", "DHR",
    "VZ", "ADBE", "CRM", "NKE", "NFLX", "TXN", "INTC", "CMCSA", "AMD", "QCOM",
    "PM", "NEE", "HON", "UNP", "RTX", "ORCL", "UPS", "IBM", "AMGN", "BA"
]


def sync_us_quotes(
    stock_codes: Optional[List[str]] = None,
    delay: float = 0.1,
    retry_failed: bool = True
):
    """同步美股行情数据"""
    logger.info("=" * 80)
    logger.info("🇺🇸 开始同步美股市场数据到MongoDB")
    logger.info("=" * 80)
    
    # 连接数据库
    import os
    mongo_uri = os.getenv("MONGODB_CONNECTION_STRING", "mongodb://admin:tradingagents123@localhost:27017/")
    client = MongoClient(mongo_uri)
    db = client.tradingagents
    
    # 获取股票列表
    codes = stock_codes if stock_codes else DEFAULT_US_STOCKS
    logger.info(f"📋 将同步 {len(codes)} 只美股")
    
    # 使用yfinance获取数据
    try:
        import yfinance as yf
    except ImportError:
        logger.error("❌ yfinance未安装，请运行: pip install yfinance")
        client.close()
        return
    
    market_quotes_coll = db.market_quotes
    screening_view_coll = db.stock_screening_view
    basic_info_coll = db.stock_basic_info
    
    total = len(codes)
    success_count = 0
    failed_count = 0
    failed_codes = []
    
    for i, code in enumerate(codes, 1):
        try:
            if i > 1:
                time.sleep(delay)
            
            logger.info(f"🔍 [{i}/{total}] 获取 {code} 数据...")
            
            ticker = yf.Ticker(code)
            info = ticker.info
            
            if not info or 'regularMarketPrice' not in info:
                logger.warning(f"⚠️  [{i}/{total}] {code}: 无法获取行情")
                failed_codes.append(code)
                failed_count += 1
                continue
            
            # 构建行情数据
            quote_data = {
                "code": code,
                "symbol": code,
                "source": "yfinance",
                "trade_date": datetime.now().strftime('%Y-%m-%d'),
                "close": info.get('regularMarketPrice'),
                "open": info.get('regularMarketOpen'),
                "high": info.get('regularMarketDayHigh'),
                "low": info.get('regularMarketDayLow'),
                "volume": info.get('regularMarketVolume'),
                "amount": info.get('regularMarketVolume', 0) * info.get('regularMarketPrice', 0) if info.get('regularMarketVolume') and info.get('regularMarketPrice') else None,
                "pct_chg": info.get('regularMarketChangePercent'),
                "market_cap": info.get('marketCap'),
                "pe": info.get('trailingPE'),
                "pb": info.get('priceToBook'),
                "updated_at": datetime.utcnow()
            }
            
            # 更新market_quotes
            market_quotes_coll.update_one(
                {"code": code, "source": "yfinance"},
                {"$set": quote_data},
                upsert=True
            )
            
            # 更新或插入basic_info
            basic_info_data = {
                "code": code,
                "symbol": code,
                "name": info.get('longName') or info.get('shortName') or code,
                "area": "USA",
                "industry": info.get('industry', ''),
                "market": info.get('exchange', 'US'),
                "source": "yfinance",
                "market_info": {"market": "US"},
                "updated_at": datetime.utcnow()
            }
            basic_info_coll.update_one(
                {"code": code},
                {"$set": basic_info_data},
                upsert=True
            )
            
            # stock_screening_view will automatically reflect the changes
            
            success_count += 1
            logger.info(f"✅ [{i}/{total}] {code}: {info.get('shortName')} - ${quote_data['close']:.2f}")
            
        except Exception as e:
            logger.error(f"❌ [{i}/{total}] {code}: {e}")
            failed_codes.append(code)
            failed_count += 1
    
    # 汇总报告
    logger.info("=" * 80)
    logger.info("✅ 美股数据同步完成")
    logger.info("=" * 80)
    logger.info(f"总数: {total}")
    logger.info(f"成功: {success_count} ({success_count*100/total:.1f}%)")
    logger.info(f"失败: {failed_count} ({failed_count*100/total:.1f}%)")
    
    if failed_codes:
        logger.warning(f"\n失败的股票: {failed_codes}")
    
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="同步美股市场数据到MongoDB")
    parser.add_argument("--delay", type=float, default=0.1, help="请求延迟（秒）")
    parser.add_argument("--no-retry", action="store_true", help="不重试失败的股票")
    parser.add_argument("--stock-codes", type=str, help="指定股票代码（逗号分隔），如: AAPL,TSLA,MSFT")
    
    args = parser.parse_args()
    
    stock_codes = None
    if args.stock_codes:
        stock_codes = [code.strip().upper() for code in args.stock_codes.split(',')]
    
    sync_us_quotes(
        stock_codes=stock_codes,
        delay=args.delay,
        retry_failed=not args.no_retry
    )

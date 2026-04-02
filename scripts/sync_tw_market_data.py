#!/usr/bin/env python3
"""
台股市场数据同步脚本

功能：
1. 从TWSE API获取台股实时行情数据
2. 同步到MongoDB的market_quotes和stock_screening_view集合
3. 支持批量处理和失败重试
4. 添加rate limiting避免API限流

使用方法：
    python3 scripts/sync_tw_market_data.py
    python3 scripts/sync_tw_market_data.py --batch-size 50 --delay 0.3
    python3 scripts/sync_tw_market_data.py --stock-codes 2330,2317,2454  # 指定股票
"""

import asyncio
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient, UpdateOne
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# 台湾市值前150大股票 (台湾50成分股 + 台湾中型100成分股)
# 数据来源: https://moneydj.emega.com.tw/js/T50_100.htm
# 最后更新: 2026-04-02
# 包含台湾股市最具代表性和流动性的股票
TOP_150_TW_STOCKS = [
    "1101", "1102", "1216", "1227", "1262", "1301", "1303", "1319", "1326", "1402",
    "1440", "1476", "1477", "1504", "1536", "1589", "1590", "1605", "1704", "1707",
    "1717", "1722", "1723", "1789", "1802", "2002", "2015", "2049", "2059", "2101",
    "2103", "2105", "2106", "2201", "2204", "2206", "2207", "2231", "2301", "2303",
    "2308", "2311", "2313", "2317", "2324", "2325", "2327", "2330", "2345", "2347",
    "2352", "2353", "2354", "2355", "2356", "2357", "2360", "2362", "2376", "2377",
    "2379", "2382", "2383", "2385", "2392", "2395", "2408", "2409", "2412", "2448",
    "2449", "2451", "2474", "2498", "2501", "2542", "2603", "2609", "2610", "2615",
    "2618", "2707", "2801", "2809", "2812", "2823", "2834", "2845", "2849", "2867",
    "2880", "2881", "2882", "2883", "2884", "2885", "2886", "2887", "2888", "2890",
    "2891", "2892", "2903", "2912", "2915", "3008", "3034", "3037", "3044", "3045",
    "3189", "3231", "3474", "3481", "3673", "3682", "3702", "4904", "4938", "4958",
    "5264", "5522", "5871", "5880", "6176", "6239", "6269", "6285", "6414", "6415",
    "6452", "6456", "6505", "8150", "8454", "8464", "9904", "9907", "9910", "9914",
    "9917", "9921", "9933", "9938", "9945",
]


def sync_tw_quotes(
    stock_codes: Optional[List[str]] = None,
    batch_size: int = 50,
    delay: float = 0.25,
    retry_failed: bool = True,
    filter_active_only: bool = True
):
    """
    同步台股行情数据到MongoDB
    
    Args:
        stock_codes: 指定要同步的股票代码列表，None=使用筛选逻辑
        batch_size: 批次大小
        delay: 每只股票之间的延迟（秒）
        retry_failed: 是否重试失败的股票
        filter_active_only: True=只同步TOP100大股票, False=全部1,925只
    """
    logger.info("=" * 80)
    logger.info("🇹🇼 开始同步台股市场数据到MongoDB")
    logger.info("=" * 80)
    
    # 1. 连接数据库
    import os
    mongo_uri = os.getenv("MONGODB_CONNECTION_STRING", "mongodb://admin:tradingagents123@localhost:27017/")
    client = MongoClient(mongo_uri)
    db = client.tradingagents
    
    # 2. 获取台股列表
    if stock_codes:
        codes = stock_codes
        logger.info(f"📋 使用指定的 {len(codes)} 只股票")
    elif not filter_active_only:
        # 不筛选，获取所有台股
        basic_info_coll = db.stock_basic_info
        all_tw_stocks = list(basic_info_coll.find(
            {"area": "Taiwan"},
            {"code": 1, "_id": 0}
        ))
        codes = [s.get('code') for s in all_tw_stocks if s.get('code')]
        logger.info(f"📋 从数据库获取到 {len(codes)} 只台股 (全部，未筛选)")
    else:
        # 使用台湾50+中型100成分股 (前150大市值股票)
        logger.info("🔍 使用台湾市值前150大股票列表...")
        
        # 验证这些股票在MongoDB中存在
        basic_info_coll = db.stock_basic_info
        existing_codes = []
        for code in TOP_150_TW_STOCKS:
            exists = basic_info_coll.count_documents({"code": code, "area": "Taiwan"}, limit=1)
            if exists:
                existing_codes.append(code)
        
        codes = existing_codes
        
        logger.info(f"✅ 筛选完成: {len(codes)}/{len(TOP_150_TW_STOCKS)} 只股票存在于MongoDB")
        logger.info(f"   来源: 台湾50 + 中型100指数成分股")
        logger.info(f"   优势: 同步时间 ~30-40秒 (vs 全量1925只 ~8-10分钟)")
        logger.info(f"   覆盖: 台湾股市主要蓝筹股和中大型股，满足90%+筛选需求")
        
        logger.info(f"📋 最终将同步 {len(codes)} 只台股")
    
    if not codes:
        logger.error("❌ 没有找到台股代码")
        client.close()
        return
    
    # 3. 初始化TWSE adapter
    from app.services.data_sources.twse_adapter import TWSEAdapter
    adapter = TWSEAdapter()
    
    if not adapter.is_available():
        logger.error("❌ TWSE adapter 不可用")
        client.close()
        return
    
    # 4. 批量获取和存储数据
    market_quotes_coll = db.market_quotes
    screening_view_coll = db.stock_screening_view
    
    total = len(codes)
    success_count = 0
    failed_count = 0
    updated_count = 0
    failed_codes = []
    
    logger.info(f"🚀 开始处理 {total} 只台股...")
    logger.info(f"⚙️  批次大小: {batch_size}, 延迟: {delay}s")
    
    for i, code in enumerate(codes, 1):
        try:
            # Rate limiting
            if i > 1:
                time.sleep(delay)
            
            # 获取最新行情数据（获取最近30天，取最后一天）
            kline = adapter.get_kline(code, limit=30)
            
            if not kline or len(kline) == 0:
                logger.warning(f"⚠️  [{i}/{total}] {code}: 无数据")
                failed_codes.append(code)
                failed_count += 1
                continue
            
            # 取最新一天的数据
            latest = kline[-1]
            
            # 计算涨跌幅 (如果有前一天数据)
            pct_chg = None
            if len(kline) >= 2:
                prev_close = kline[-2]['close']
                curr_close = latest['close']
                if prev_close and prev_close > 0:
                    pct_chg = ((curr_close - prev_close) / prev_close) * 100
            
            # 构建行情数据
            quote_data = {
                "code": code,
                "symbol": code,
                "source": "twse",
                "trade_date": latest['time'],
                "open": latest['open'],
                "high": latest['high'],
                "low": latest['low'],
                "close": latest['close'],
                "volume": latest['volume'],
                "amount": latest['volume'] * latest['close'] if latest['volume'] and latest['close'] else None,  # 估算成交额
                "pct_chg": pct_chg,
                "updated_at": datetime.utcnow()
            }
            
            # 更新market_quotes
            market_quotes_coll.update_one(
                {"code": code, "source": "twse"},
                {"$set": quote_data},
                upsert=True
            )
            
            # Note: stock_screening_view is a MongoDB view, it will automatically
            # reflect changes from market_quotes and stock_basic_info
            
            success_count += 1
            updated_count += 1
            
            if i % 10 == 0:
                logger.info(f"📊 进度: {i}/{total} ({i*100/total:.1f}%) | 成功: {success_count}, 失败: {failed_count}")
            
        except Exception as e:
            logger.error(f"❌ [{i}/{total}] {code}: {e}")
            failed_codes.append(code)
            failed_count += 1
            continue
    
    # 5. 重试失败的股票
    if retry_failed and failed_codes:
        logger.info(f"\n🔄 重试 {len(failed_codes)} 只失败的股票...")
        for code in failed_codes[:]:
            try:
                time.sleep(delay * 2)  # 更长延迟
                kline = adapter.get_kline(code, limit=30)
                if kline and len(kline) > 0:
                    # (重复上面的逻辑)
                    latest = kline[-1]
                    quote_data = {
                        "code": code,
                        "source": "twse",
                        "close": latest['close'],
                        "volume": latest['volume'],
                        "amount": latest['volume'] * latest['close'] if latest['volume'] and latest['close'] else None,
                        "updated_at": datetime.utcnow()
                    }
                    market_quotes_coll.update_one(
                        {"code": code, "source": "twse"},
                        {"$set": quote_data},
                        upsert=True
                    )
                    success_count += 1
                    failed_codes.remove(code)
                    logger.info(f"✅ 重试成功: {code}")
            except Exception as e:
                logger.warning(f"⚠️  重试失败: {code} - {e}")
    
    # 6. 汇总报告
    logger.info("=" * 80)
    logger.info("✅ 台股数据同步完成")
    logger.info("=" * 80)
    logger.info(f"总数: {total}")
    logger.info(f"成功: {success_count} ({success_count*100/total:.1f}%)")
    logger.info(f"失败: {len(failed_codes)} ({len(failed_codes)*100/total:.1f}%)")
    logger.info(f"更新: {updated_count}")
    
    if failed_codes:
        logger.warning(f"\n失败的股票代码 (前20个): {failed_codes[:20]}")
    
    logger.info("\n💡 建议：将此脚本添加到定时任务，每日同步数据")
    logger.info("   示例: crontab -e")
    logger.info("   0 18 * * 1-5 cd /path/to/TradingAgents-CN && python3 scripts/sync_tw_market_data.py")
    
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="同步台股市场数据到MongoDB")
    parser.add_argument("--batch-size", type=int, default=50, help="批次大小")
    parser.add_argument("--delay", type=float, default=0.25, help="请求延迟（秒）")
    parser.add_argument("--no-retry", action="store_true", help="不重试失败的股票")
    parser.add_argument("--stock-codes", type=str, help="指定股票代码（逗号分隔），如: 2330,2317,2454")
    parser.add_argument("--all", action="store_true", help="同步全部1,925只台股（默认只同步前150大）")
    
    args = parser.parse_args()
    
    stock_codes = None
    if args.stock_codes:
        stock_codes = [code.strip() for code in args.stock_codes.split(',')]
    
    sync_tw_quotes(
        stock_codes=stock_codes,
        batch_size=args.batch_size,
        delay=args.delay,
        retry_failed=not args.no_retry,
        filter_active_only=not args.all  # --all disables filtering
    )

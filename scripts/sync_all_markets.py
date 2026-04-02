#!/usr/bin/env python3
"""
统一市场数据同步脚本

一次性同步所有市场（TW/US/HK）的数据到MongoDB，实现快速筛选

使用方法：
    # 同步所有市场
    python3 scripts/sync_all_markets.py
    
    # 只同步特定市场
    python3 scripts/sync_all_markets.py --markets TW,US
    
    # 快速测试（少量股票）
    python3 scripts/sync_all_markets.py --test
"""

import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="统一同步多市场数据到MongoDB")
    parser.add_argument("--markets", type=str, default="TW,US,HK", help="要同步的市场（逗号分隔）")
    parser.add_argument("--test", action="store_true", help="测试模式（只同步少量股票）")
    parser.add_argument("--tw-delay", type=float, default=0.25, help="台股请求延迟（秒）")
    parser.add_argument("--us-delay", type=float, default=0.1, help="美股请求延迟（秒）")
    parser.add_argument("--hk-delay", type=float, default=0.15, help="港股请求延迟（秒）")
    
    args = parser.parse_args()
    
    markets = [m.strip().upper() for m in args.markets.split(',')]
    
    logger.info("=" * 80)
    logger.info("🌐 统一市场数据同步")
    logger.info("=" * 80)
    logger.info(f"📋 将同步市场: {', '.join(markets)}")
    logger.info(f"🧪 测试模式: {'是' if args.test else '否'}")
    logger.info("=" * 80)
    print()
    
    # Sync TW market
    if "TW" in markets:
        logger.info("\n" + "🇹🇼 " + "=" * 76)
        logger.info("开始同步台股数据")
        logger.info("=" * 80 + "\n")
        
        try:
            from scripts.sync_tw_market_data import sync_tw_quotes
            
            if args.test:
                # Test mode: only sync a few stocks
                test_codes = ["2330", "2317", "2454", "1240", "1259"]
                logger.info(f"🧪 测试模式：只同步 {len(test_codes)} 只台股")
                sync_tw_quotes(stock_codes=test_codes, delay=args.tw_delay, retry_failed=False)
            else:
                # Full sync
                sync_tw_quotes(delay=args.tw_delay, retry_failed=True)
            
            logger.info("✅ 台股同步完成\n")
        except Exception as e:
            logger.error(f"❌ 台股同步失败: {e}\n")
    
    # Sync US market
    if "US" in markets:
        logger.info("\n" + "🇺🇸 " + "=" * 76)
        logger.info("开始同步美股数据")
        logger.info("=" * 80 + "\n")
        
        try:
            from scripts.sync_us_market_data import sync_us_quotes
            
            if args.test:
                test_codes = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"]
                logger.info(f"🧪 测试模式：只同步 {len(test_codes)} 只美股")
                sync_us_quotes(stock_codes=test_codes, delay=args.us_delay, retry_failed=False)
            else:
                sync_us_quotes(delay=args.us_delay, retry_failed=True)
            
            logger.info("✅ 美股同步完成\n")
        except Exception as e:
            logger.error(f"❌ 美股同步失败: {e}\n")
    
    # Sync HK market
    if "HK" in markets:
        logger.info("\n" + "🇭🇰 " + "=" * 76)
        logger.info("开始同步港股数据")
        logger.info("=" * 80 + "\n")
        
        try:
            from scripts.sync_hk_market_data import sync_hk_quotes
            
            if args.test:
                test_codes = ["0700", "9988", "1398", "3690", "1299"]
                logger.info(f"🧪 测试模式：只同步 {len(test_codes)} 只港股")
                sync_hk_quotes(stock_codes=test_codes, delay=args.hk_delay, retry_failed=False)
            else:
                sync_hk_quotes(delay=args.hk_delay, retry_failed=True)
            
            logger.info("✅ 港股同步完成\n")
        except Exception as e:
            logger.error(f"❌ 港股同步失败: {e}\n")
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("🎉 所有市场数据同步完成！")
    logger.info("=" * 80)
    logger.info("\n📋 下一步：")
    logger.info("   1. 重启后端服务以刷新缓存")
    logger.info("   2. 前端进行股票筛选测试")
    logger.info("   3. 现在筛选速度应该和A股一样快了！")
    logger.info("\n💡 建议：添加到定时任务，每日自动同步")
    logger.info("   crontab: 0 18 * * 1-5 python3 scripts/sync_all_markets.py")


if __name__ == "__main__":
    main()

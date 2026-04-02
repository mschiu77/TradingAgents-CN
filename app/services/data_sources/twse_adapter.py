"""
TWSE (Taiwan Stock Exchange) data source adapter
Uses twstock library for Taiwan stock market data
"""
from typing import Optional, Dict
import logging
from datetime import datetime, timedelta
import pandas as pd

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)

# 🔥 Patch twstock URLs at module import time (before any usage)
try:
    import twstock.stock as _stock_module
    if hasattr(_stock_module, 'TWSE_BASE_URL') and _stock_module.TWSE_BASE_URL.startswith('http://'):
        _stock_module.TWSE_BASE_URL = 'https://www.twse.com.tw/'
        logger.info("✅ TWSE: Patched TWSE_BASE_URL to HTTPS at module load")
    if hasattr(_stock_module, 'TPEX_BASE_URL') and _stock_module.TPEX_BASE_URL.startswith('http://'):
        _stock_module.TPEX_BASE_URL = 'https://www.tpex.org.tw/'
        logger.info("✅ TWSE: Patched TPEX_BASE_URL to HTTPS at module load")
except Exception as e:
    logger.warning(f"⚠️ TWSE: Failed to patch URLs at module load: {e}")


class TWSEAdapter(DataSourceAdapter):
    """TWSE (Taiwan Stock Exchange) data source adapter"""

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "twse"

    def _get_default_priority(self) -> int:
        return 3  # Medium priority

    def is_available(self) -> bool:
        """Check if twstock library is available"""
        try:
            import twstock  # noqa: F401
            return True
        except ImportError:
            logger.warning("twstock library not installed. Install with: pip install twstock")
            return False

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """Get Taiwan stock list"""
        if not self.is_available():
            return None
        
        try:
            import twstock
            
            logger.info("🇹🇼 TWSE: Fetching stock list...")
            
            # Get all stock codes
            codes = twstock.codes
            
            stock_list = []
            for code, info in codes.items():
                # Filter for stocks only (exclude ETFs, etc.)
                if info.type == '股票':
                    stock_list.append({
                        'symbol': code,
                        'ts_code': f"{code}.TW",  # Taiwan stock format
                        'name': info.name,
                        'industry': info.group if hasattr(info, 'group') else '',
                        'area': 'Taiwan',
                        'market': info.market if hasattr(info, 'market') else 'TSE'
                    })
            
            if not stock_list:
                logger.warning("TWSE: No stocks found")
                return None
            
            df = pd.DataFrame(stock_list)
            logger.info(f"✅ TWSE: Found {len(df)} stocks")
            return df
            
        except Exception as e:
            logger.error(f"❌ TWSE: Failed to fetch stock list: {e}")
            return None

    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """Get daily basic financial data for a specific date"""
        if not self.is_available():
            return None
        
        try:
            import twstock
            
            # Convert date format from YYYYMMDD to datetime
            date_obj = datetime.strptime(trade_date, '%Y%m%d')
            
            logger.info(f"🇹🇼 TWSE: Fetching daily basic data for {trade_date}...")
            
            codes = twstock.codes
            basic_data = []
            
            for code, info in codes.items():
                if info.type == '股票':
                    try:
                        stock = twstock.Stock(code)
                        # Get the latest trading data
                        data = stock.fetch_from(date_obj.year, date_obj.month)
                        
                        if data and len(data) > 0:
                            latest = data[-1]
                            basic_data.append({
                                'ts_code': f"{code}.TW",
                                'trade_date': trade_date,
                                'close': latest.close,
                                'turnover_rate': None,  # Not available in twstock
                                'pe': None,  # Not available in twstock
                                'pb': None,  # Not available in twstock
                                'total_mv': None,  # Market value not directly available
                            })
                    except Exception as e:
                        logger.debug(f"TWSE: Failed to fetch data for {code}: {e}")
                        continue
            
            if not basic_data:
                return None
            
            df = pd.DataFrame(basic_data)
            logger.info(f"✅ TWSE: Fetched basic data for {len(df)} stocks")
            return df
            
        except Exception as e:
            logger.error(f"❌ TWSE: Failed to fetch daily basic data: {e}")
            return None

    def find_latest_trade_date(self) -> Optional[str]:
        """Find the latest trading date"""
        if not self.is_available():
            return None
        
        try:
            import twstock
            
            # Get a sample stock (台積電 2330) to check latest date
            stock = twstock.Stock('2330')
            today = datetime.now()
            
            # Try to get data from the last 7 days
            data = stock.fetch_from(today.year, today.month)
            
            if data and len(data) > 0:
                latest = data[-1]
                latest_date = latest.date.strftime('%Y%m%d')
                logger.info(f"✅ TWSE: Latest trade date is {latest_date}")
                return latest_date
            
            return None
            
        except Exception as e:
            logger.error(f"❌ TWSE: Failed to find latest trade date: {e}")
            return None

    def get_realtime_quotes(self) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """Get real-time quotes for all stocks"""
        if not self.is_available():
            return None
        
        try:
            import twstock
            
            logger.info("🇹🇼 TWSE: Fetching real-time quotes...")
            
            codes = twstock.codes
            quotes = {}
            
            for code, info in codes.items():
                if info.type == '股票':
                    try:
                        stock = twstock.Stock(code)
                        # Get latest price
                        price = stock.price
                        
                        if price and len(price) > 0:
                            latest_price = price[-1]
                            prev_price = price[-2] if len(price) > 1 else latest_price
                            
                            pct_chg = ((latest_price - prev_price) / prev_price * 100) if prev_price > 0 else 0
                            
                            quotes[code] = {
                                'close': latest_price,
                                'pct_chg': pct_chg,
                                'amount': None  # Volume data not readily available in realtime
                            }
                    except Exception as e:
                        logger.debug(f"TWSE: Failed to fetch quote for {code}: {e}")
                        continue
            
            if not quotes:
                return None
            
            logger.info(f"✅ TWSE: Fetched quotes for {len(quotes)} stocks")
            return quotes
            
        except Exception as e:
            logger.error(f"❌ TWSE: Failed to fetch realtime quotes: {e}")
            return None

    def get_kline(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None):
        """Get K-line data for a stock"""
        if not self.is_available():
            return None
        
        try:
            import twstock
            import time
            
            # 🔥 Rate limiting: Add delay to avoid TWSE API blocking
            if not hasattr(self, '_last_request_time'):
                self._last_request_time = 0
            
            elapsed = time.time() - self._last_request_time
            if elapsed < 0.2:  # Minimum 200ms between requests
                time.sleep(0.2 - elapsed)
            
            # Remove .TW suffix if present
            code = code.replace('.TW', '')
            
            logger.info(f"🇹🇼 TWSE: Fetching K-line for {code}, period={period}, limit={limit}")
            
            self._last_request_time = time.time()
            stock = twstock.Stock(code)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=limit * 2)  # Get extra days to ensure enough data
            
            # Fetch historical data
            data = stock.fetch_from(start_date.year, start_date.month)
            
            if not data:
                return None
            
            # Convert to required format
            kline_data = []
            for record in data[-limit:]:  # Get last 'limit' records
                kline_data.append({
                    'time': record.date.strftime('%Y-%m-%d'),
                    'open': record.open,
                    'high': record.high,
                    'low': record.low,
                    'close': record.close,
                    'volume': record.capacity,
                    'amount': None  # Amount not available
                })
            
            logger.info(f"✅ TWSE: Fetched {len(kline_data)} K-line records for {code}")
            return kline_data
            
        except Exception as e:
            logger.error(f"❌ TWSE: Failed to fetch K-line for {code}: {e}")
            return None

    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        """Get news and announcements for a stock"""
        # Note: twstock doesn't provide news data
        # You would need to integrate with another API (e.g., Taiwan news APIs or scraping)
        logger.warning("TWSE: News data not supported by twstock library")
        return []

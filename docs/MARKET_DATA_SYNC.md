# Market Data Sync Guide

## Overview

To enable **fast MongoDB-based screening** for TW/US/HK stocks (like CN stocks), you need to sync trading data to MongoDB first.

## Current Status

| Market | Basic Info | Trading Data | Screening Speed |
|--------|-----------|--------------|-----------------|
| CN (A股) | ✅ 7,422 | ✅ Complete | ⚡ Fast (MongoDB) |
| TW (台股) | ✅ 1,925 | ❌ Missing | 🐢 Slow (API) |
| HK (港股) | ❌ 0 | ❌ Missing | 🐢 Slow (API) |
| US (美股) | ❌ 0 | ❌ Missing | 🐢 Slow (API) |

**Trading Data** = amount, close, volume, pe, pb, pct_chg (required for screening)

---

## Quick Start - Sync All Markets

### Test Mode (Quick - ~30 seconds)
```bash
cd /home/ubuntu/mingshuoqiu/TradingAgents-CN
source venv/bin/activate
python3 scripts/sync_all_markets.py --test
```

This syncs:
- 5 TW stocks (2330, 2317, 2454, 1240, 1259)
- 5 US stocks (AAPL, TSLA, MSFT, GOOGL, AMZN)
- 5 HK stocks (0700, 9988, 1398, 3690, 1299)

### Full Sync (Complete - ~30-60 minutes)
```bash
python3 scripts/sync_all_markets.py
```

This syncs:
- **1,925 TW stocks** (~8-10 minutes with rate limiting)
- **50 US stocks** (~1 minute)
- **15 HK stocks** (~30 seconds)

---

## Individual Market Sync

### Taiwan Stocks (台股)
```bash
# Full sync (all 1,925 stocks)
python3 scripts/sync_tw_market_data.py

# Specific stocks
python3 scripts/sync_tw_market_data.py --stock-codes 2330,2317,2454

# Adjust rate limiting
python3 scripts/sync_tw_market_data.py --delay 0.3  # Slower but safer
```

**Time estimate:** 1,925 stocks × 0.25s = ~8 minutes

### US Stocks (美股)
```bash
# Top 50 US stocks (default)
python3 scripts/sync_us_market_data.py

# Specific stocks
python3 scripts/sync_us_market_data.py --stock-codes AAPL,TSLA,NVDA,MSFT

# Custom list
python3 scripts/sync_us_market_data.py --stock-codes "$(cat my_stocks.txt)"
```

**Time estimate:** 50 stocks × 0.1s = ~5 seconds

### Hong Kong Stocks (港股)
```bash
# Top 15 HK stocks (default)
python3 scripts/sync_hk_market_data.py

# Specific stocks
python3 scripts/sync_hk_market_data.py --stock-codes 0700,9988,1398
```

**Time estimate:** 15 stocks × 0.15s = ~2 seconds

---

## What Gets Synced

Each script populates MongoDB with:

### 1. market_quotes collection
```javascript
{
  code: "2330",
  symbol: "2330.TW",
  source: "twse",
  close: 1855.0,
  volume: 46457423,
  amount: 86158929665,  // volume × close
  pct_chg: 0.81,
  pe: 28.5,
  pb: 8.2,
  market_cap: 48123456789,
  updated_at: ISODate("2026-04-02T04:30:00Z")
}
```

### 2. stock_basic_info collection
Updates existing records or creates new ones with:
- name, industry, area, market
- market_info.market = "TW"/"US"/"HK"

### 3. stock_screening_view collection
Merged view of basic_info + quotes for fast screening

---

## After Syncing

### Verify Data
```bash
# Check TW stocks have trading data
python3 << 'EOF'
from pymongo import MongoClient
import os
mongo_uri = os.getenv("MONGODB_CONNECTION_STRING", "mongodb://admin:tradingagents123@localhost:27017/")
client = MongoClient(mongo_uri)
db = client.tradingagents

# Check if amount field exists
sample = db.stock_screening_view.find_one(
    {"area": "Taiwan", "amount": {"$ne": None}}
)
print(f"TW stock with amount: {sample['code'] if sample else 'None found'}")
if sample:
    print(f"  close: {sample.get('close')}")
    print(f"  amount: {sample.get('amount')}")
    print(f"  volume: {sample.get('volume')}")
client.close()
EOF
```

### Test Screening
1. Restart backend: `docker-compose restart backend` or restart Python
2. Frontend: Go to 股票筛选
3. Select TW market
4. Add condition: `成交额 > 100亿`
5. **Should now be FAST** (< 1 second) instead of 30+ seconds!

---

## Automation (Production)

Add to crontab for daily sync:

```bash
crontab -e
```

Add these lines:
```cron
# Sync TW stocks daily at 6:30 PM (after market close)
30 18 * * 1-5 cd /home/ubuntu/mingshuoqiu/TradingAgents-CN && source venv/bin/activate && python3 scripts/sync_tw_market_data.py >> logs/sync_tw.log 2>&1

# Sync US stocks daily at 6:00 AM (after US market close)
0 6 * * 1-5 cd /home/ubuntu/mingshuoqiu/TradingAgents-CN && source venv/bin/activate && python3 scripts/sync_us_market_data.py >> logs/sync_us.log 2>&1

# Sync HK stocks daily at 5:30 PM (after HK market close)
30 17 * * 1-5 cd /home/ubuntu/mingshuoqiu/TradingAgents-CN && source venv/bin/activate && python3 scripts/sync_hk_market_data.py >> logs/sync_hk.log 2>&1
```

---

## Troubleshooting

### Rate Limiting Errors
```bash
# Increase delay
python3 scripts/sync_tw_market_data.py --delay 0.5
```

### Partial Sync
If script crashes halfway, it's safe to re-run - MongoDB upsert won't duplicate data.

### Check Sync Status
```bash
python3 << 'EOF'
from pymongo import MongoClient
import os
client = MongoClient(os.getenv("MONGODB_CONNECTION_STRING", "mongodb://admin:tradingagents123@localhost:27017/"))
db = client.tradingagents

for market in ["Taiwan", "USA", "Hong Kong"]:
    count_with_amount = db.stock_screening_view.count_documents({
        "area": market,
        "amount": {"$ne": None}
    })
    total = db.stock_basic_info.count_documents({"area": market})
    print(f"{market}: {count_with_amount}/{total} stocks have trading data")
client.close()
EOF
```

---

## Performance Impact

**Before Sync (API-based):**
- TW screening: 30-60 seconds (120 stocks)
- Limited by API rate limits
- Unpredictable response times

**After Sync (MongoDB-based):**
- TW screening: < 1 second (any number of stocks)
- Same speed as CN stocks
- Instant results ⚡

**Trade-off:**
- One-time: 10-15 minutes setup
- Daily: ~5-10 minutes maintenance
- Benefit: 30x-60x faster screening forever

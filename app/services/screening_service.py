from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

# 统一指标库
from tradingagents.tools.analysis.indicators import IndicatorSpec, compute_many
# 统一多数据源DF接口（按优先级降级）
from tradingagents.dataflows.data_source_manager import get_data_source_manager
from tradingagents.dataflows.providers.china.fundamentals_snapshot import get_cn_fund_snapshot


from app.services.screening.eval_utils import (
    collect_fields_from_conditions as _collect_fields_from_conditions_util,
    evaluate_conditions as _evaluate_conditions_util,
    evaluate_fund_conditions as _evaluate_fund_conditions_util,
    safe_float as _safe_float_util,
)

# --- DSL 约束 ---
ALLOWED_FIELDS = {
    # 原始行情（统一为小写列）
    "open", "high", "low", "close", "vol", "amount",
    # 派生
    "pct_chg",  # 当日涨跌幅
    # 指标（固定参数）
    "ma5", "ma10", "ma20", "ma60",
    "ema12", "ema26",
    "dif", "dea", "macd_hist",
    "rsi14",
    "boll_mid", "boll_upper", "boll_lower",
    "atr14",
    "kdj_k", "kdj_d", "kdj_j",
    # 预留：基本面（后续实现）
    "pe", "pb", "roe", "market_cap",
}

# 分类：基础行情字段、技术指标字段、基本面字段
BASE_FIELDS = {"open", "high", "low", "close", "vol", "amount", "pct_chg"}
TECH_FIELDS = {
    "ma5", "ma10", "ma20", "ma60",
    "ema12", "ema26",
    "dif", "dea", "macd_hist",
    "rsi14",
    "boll_mid", "boll_upper", "boll_lower",
    "atr14",
    "kdj_k", "kdj_d", "kdj_j",
}
FUND_FIELDS = {"pe", "pb", "roe", "market_cap"}

ALLOWED_OPS = {">", "<", ">=", "<=", "==", "!=", "between", "cross_up", "cross_down"}


@dataclass
class ScreeningParams:
    market: str = "CN"
    date: Optional[str] = None  # YYYY-MM-DD，None=最近交易日
    adj: str = "qfq"  # 预留参数，当前实现使用Tdx数据，不区分复权
    limit: int = 50
    offset: int = 0
    order_by: Optional[List[Dict[str, str]]] = None  # [{field, direction}]


import logging
logger = logging.getLogger("agents")

class ScreeningService:
    def __init__(self):
        # 数据源通过统一DF接口获取，不直接绑定具体源
        self.provider = None

    # --- 公共入口 ---
    def run(self, conditions: Dict[str, Any], params: ScreeningParams) -> Dict[str, Any]:
        logger.info(f"🔍 [Screening] 开始筛选 - 市场: {params.market}")
        symbols = self._get_universe(params.market)
        logger.info(f"📊 [Screening] 获取到 {len(symbols)} 只{params.market}股票")
        # 为控制时长，先限制样本规模（后续用批量/缓存优化）
        symbols = symbols[:120]

        end_date = datetime.now()
        start_date = end_date - timedelta(days=220)
        end_s = end_date.strftime("%Y-%m-%d")
        start_s = start_date.strftime("%Y-%m-%d")

        results: List[Dict[str, Any]] = []

        # 解析条件中涉及的字段，决定是否需要技术指标/行情
        logger.info(f"🔍 [Screening] 原始条件: {conditions}")
        needed_fields = self._collect_fields_from_conditions(conditions)
        order_fields = {o.get("field") for o in (params.order_by or []) if o.get("field")}
        all_needed = set(needed_fields) | set(order_fields)
        need_tech = any(f in TECH_FIELDS for f in all_needed)
        need_base = any(f in BASE_FIELDS for f in all_needed) or need_tech
        need_fund = any(f in FUND_FIELDS for f in all_needed)
        
        logger.info(f"🔍 [Screening] 字段分析 - needed_fields: {needed_fields}, need_base: {need_base}, need_tech: {need_tech}, need_fund: {need_fund}")

        for code in symbols:
            try:
                dfc = None
                last = None

                # 🔥 为非中国市场添加市场后缀以便正确识别
                query_code = code
                if params.market == "TW" and not code.endswith('.TW'):
                    query_code = f"{code}.TW"
                elif params.market == "HK" and not code.endswith('.HK'):
                    query_code = f"{code}.HK"
                # US stocks usually don't need suffix

                # 如需要基础行情/技术指标才取K线
                if need_base:
                    logger.info(f"🔍 [Screening] 获取 {query_code} 的K线数据...")
                    manager = get_data_source_manager()
                    df = manager.get_stock_dataframe(query_code, start_s, end_s)
                    if df is None or df.empty:
                        logger.warning(f"⚠️ [Screening] {query_code} 无数据，跳过")
                        continue
                    logger.info(f"✅ [Screening] {query_code} 获取到 {len(df)} 条数据")
                    # 统一列为小写
                    dfu = df.rename(columns={
                        "Open": "open", "High": "high", "Low": "low", "Close": "close",
                        "Volume": "vol", "Amount": "amount"
                    }).copy()
                    # 计算派生：pct_chg
                    if "close" in dfu.columns:
                        dfu["pct_chg"] = dfu["close"].pct_change() * 100.0

                    # 仅在需要技术指标时计算
                    if need_tech:
                        specs = [
                            IndicatorSpec("ma", {"n": 5}),
                            IndicatorSpec("ma", {"n": 10}),
                            IndicatorSpec("ma", {"n": 20}),
                            IndicatorSpec("ema", {"n": 12}),
                            IndicatorSpec("ema", {"n": 26}),
                            IndicatorSpec("macd"),
                            IndicatorSpec("rsi", {"n": 14}),
                            IndicatorSpec("boll", {"n": 20, "k": 2}),
                            IndicatorSpec("atr", {"n": 14}),
                            IndicatorSpec("kdj", {"n": 9, "m1": 3, "m2": 3}),
                        ]
                        dfc = compute_many(dfu, specs)
                    else:
                        dfc = dfu

                    last = dfc.iloc[-1]

                # 评估条件（若条件完全是基本面且不涉及行情/技术，这里可跳过K线）
                passes = True
                if need_base:
                    passes = self._evaluate_conditions(dfc, conditions)
                elif need_fund and not need_base and not need_tech:
                    # 仅基本面条件：使用基本面快照判断
                    snap = get_cn_fund_snapshot(code)
                    if not snap:
                        passes = False
                    else:
                        passes = self._evaluate_fund_conditions(snap, conditions)

                if passes:
                    item = {"code": code}
                    if last is not None:
                        item.update({
                            "close": self._safe_float(last.get("close")),
                            "pct_chg": self._safe_float(last.get("pct_chg")),
                            "amount": self._safe_float(last.get("amount")),
                            "ma20": self._safe_float(last.get("ma20")) if need_tech else None,
                            "rsi14": self._safe_float(last.get("rsi14")) if need_tech else None,
                            "kdj_k": self._safe_float(last.get("kdj_k")) if need_tech else None,
                            "kdj_d": self._safe_float(last.get("kdj_d")) if need_tech else None,
                            "kdj_j": self._safe_float(last.get("kdj_j")) if need_tech else None,
                            "dif": self._safe_float(last.get("dif")) if need_tech else None,
                            "dea": self._safe_float(last.get("dea")) if need_tech else None,
                            "macd_hist": self._safe_float(last.get("macd_hist")) if need_tech else None,
                        })
                    results.append(item)
            except Exception:
                continue

        total = len(results)
        # 排序
        if params.order_by:
            for order in reversed(params.order_by):  # 后者优先级低
                f = order.get("field")
                d = order.get("direction", "desc").lower()
                if f in ALLOWED_FIELDS:
                    results.sort(key=lambda x: (x.get(f) is None, x.get(f)), reverse=(d == "desc"))

        # 分页
        start = params.offset or 0
        end = start + (params.limit or 50)
        page_items = results[start:end]

        return {
            "total": total,
            "items": page_items,
        }
    def _evaluate_fund_conditions(self, snap: Dict[str, Any], node: Dict[str, Any]) -> bool:
        """Delegate fundamental condition evaluation to utils to keep service slim."""
        return _evaluate_fund_conditions_util(snap, node, FUND_FIELDS)


    def _collect_fields_from_conditions(self, node: Dict[str, Any]) -> List[str]:
        """Delegate field collection to utils."""
        return _collect_fields_from_conditions_util(node, ALLOWED_FIELDS)

    # --- 内部：DSL 评估 ---
    def _evaluate_conditions(self, df: pd.DataFrame, node: Dict[str, Any]) -> bool:
        """Delegate technical/base condition evaluation to utils."""
        return _evaluate_conditions_util(df, node, ALLOWED_FIELDS, ALLOWED_OPS)

    # --- 工具 ---
    def _safe_float(self, v: Any) -> Optional[float]:
        """Delegate numeric coercion to utils."""
        return _safe_float_util(v)

    def _get_universe(self, market: str = "CN") -> List[str]:
        """获取指定市场的股票代码集合：从 MongoDB stock_basic_info 集合获取"""
        logger.info(f"🔍 [_get_universe] 查询市场: {market}")
        try:
            # Use synchronous MongoDB client to avoid async issues
            from pymongo import MongoClient
            import os
            
            mongo_uri = os.getenv("MONGODB_CONNECTION_STRING", "mongodb://admin:tradingagents123@localhost:27017/")
            client = MongoClient(mongo_uri)
            db = client.tradingagents
            collection = db.stock_basic_info

            # 根据市场类型构建查询条件
            if market == "CN":
                # A股股票代码
                query = {
                    "$or": [
                        {"market_info.market": "CN"},
                        {"category": "stock_cn"},
                        {"market": {"$in": ["主板", "创业板", "科创板", "北交所"]}}
                    ]
                }
                market_name = "A股"
            elif market == "TW":
                # 台股股票代码
                query = {
                    "$or": [
                        {"market_info.market": "TW"},
                        {"ts_code": {"$regex": r"\.TW$"}},
                        {"area": "Taiwan"}
                    ]
                }
                market_name = "台股"
            elif market == "HK":
                # 港股股票代码
                query = {
                    "$or": [
                        {"market_info.market": "HK"},
                        {"ts_code": {"$regex": r"\.HK$"}}
                    ]
                }
                market_name = "港股"
            elif market == "US":
                # 美股股票代码
                query = {
                    "$or": [
                        {"market_info.market": "US"},
                        {"area": "USA"}
                    ]
                }
                market_name = "美股"
            else:
                logger.warning(f"⚠️ 不支持的市场类型: {market}，使用A股")
                return self._get_universe("CN")
            
            logger.info(f"🔍 [_get_universe] 查询条件: {query}")
            cursor = collection.find(query, {"code": 1, "symbol": 1, "_id": 0})

            # 同步获取所有股票代码
            codes = []
            for doc in cursor:
                code = doc.get("code") or doc.get("symbol")
                if code:
                    codes.append(code)

            # Close connection
            client.close()

            if codes:
                logger.info(f"📊 从 MongoDB 获取到 {len(codes)} 只{market_name}股票")
                return codes
            else:
                # 如果数据库为空，返回默认股票代码
                logger.warning(f"⚠️ MongoDB 中未找到{market_name}数据")
                if market == "TW":
                    return ["2330", "2317", "2454"]  # 台积电、鸿海、联发科
                elif market == "HK":
                    return ["00700", "09988"]  # 腾讯、阿里
                elif market == "US":
                    return ["AAPL", "TSLA"]
                else:
                    return ["000001", "000002", "600519"]  # A股

        except Exception as e:
            logger.error(f"❌ 从 MongoDB 获取股票列表失败: {e}")
            # 异常时返回常见股票代码作为兜底
            return ["000001", "000002", "000858", "600519", "600036", "601318", "300750"]


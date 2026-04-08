"""
回测服务
执行策略回测并返回结果
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
from io import StringIO

logger = logging.getLogger(__name__)


class BacktestService:
    """回测服务"""
    
    def __init__(self):
        pass
    
    async def run_backtest(
        self,
        strategy_code: str,
        market: str,
        start_date: str,
        end_date: str,
        initial_capital: float,
        commission_rate: float,
        slippage: float
    ) -> Dict[str, Any]:
        """
        运行策略回测
        
        Args:
            strategy_code: 策略代码
            market: 市场类型
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            commission_rate: 手续费率
            slippage: 滑点
        
        Returns:
            回测结果字典
        """
        logger.info(f"🚀 开始回测 - 市场:{market}, 日期:{start_date}~{end_date}")
        
        try:
            # 1. 获取历史数据
            data = await self._fetch_historical_data(market, start_date, end_date)
            if data is None or len(data) == 0:
                raise Exception("无法获取历史数据")
            
            logger.info(f"✅ 获取历史数据: {len(data)} 条记录")
            
            # 2. 执行策略
            strategy_instance, equity_curve, trades = await self._execute_strategy(
                strategy_code,
                data,
                initial_capital
            )
            
            # 3. 计算回测指标
            results = self._calculate_metrics(
                equity_curve,
                trades,
                initial_capital,
                commission_rate,
                slippage
            )
            
            logger.info(f"✅ 回测完成 - 收益率: {results['total_return_pct']:.2f}%")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 回测失败: {e}", exc_info=True)
            raise
    
    async def _fetch_historical_data(
        self,
        market: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """获取历史数据"""
        from app.core.database import get_mongo_db
        
        db = get_mongo_db()
        
        # 构建查询条件
        query = {
            "trade_date": {
                "$gte": start_date.replace("-", ""),
                "$lte": end_date.replace("-", "")
            }
        }
        
        # 根据市场类型添加过滤
        if market == "CN":
            query["$or"] = [
                {"ts_code": {"$regex": r"\.(SH|SZ)$"}},
                {"code": {"$regex": r"^(6|0|3)\d{5}$"}}
            ]
        elif market == "TW":
            query["source"] = "twse"
        elif market == "HK":
            query["$or"] = [
                {"ts_code": {"$regex": r"\.HK$"}},
                {"code": {"$regex": r"^0\d{4}$"}}
            ]
        elif market == "US":
            query["market"] = "US"
        
        # 查询数据
        cursor = db["market_quotes"].find(query).sort("trade_date", 1)
        records = await cursor.to_list(length=None)
        
        if not records:
            logger.warning(f"⚠️ 未找到历史数据: market={market}, {start_date}~{end_date}")
            return pd.DataFrame()
        
        # 转换为DataFrame
        df = pd.DataFrame(records)
        
        # 标准化列名
        df = df.rename(columns={
            "trade_date": "date",
            "ts_code": "code"
        })
        
        # 确保必要的列存在
        required_cols = ["date", "code", "open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                if col == "volume":
                    df[col] = df.get("amount", 0)
                else:
                    logger.warning(f"⚠️ 缺少列: {col}")
        
        return df[required_cols]
    
    async def _execute_strategy(
        self,
        strategy_code: str,
        data: pd.DataFrame,
        initial_capital: float
    ):
        """执行策略代码"""
        from app.services.strategy_generator import BASE_STRATEGY_CLASS
        
        # 准备执行环境
        exec_globals = {
            "pd": pd,
            "np": np,
            "ta": None,  # talib may not be available
            "print": lambda *args: None  # Suppress print
        }
        
        # 执行基类定义
        exec(BASE_STRATEGY_CLASS, exec_globals)
        
        # 执行策略代码
        exec(strategy_code, exec_globals)
        
        # 获取策略类
        if "Strategy" not in exec_globals:
            raise Exception("策略代码中未找到Strategy类")
        
        StrategyClass = exec_globals["Strategy"]
        strategy = StrategyClass(initial_capital=initial_capital)
        
        # 按日期和股票分组
        dates = sorted(data["date"].unique())
        
        equity_curve = []
        
        # 逐日回测
        for date in dates:
            # 获取当天所有股票的数据
            day_data = data[data["date"] == date]
            
            # 获取每只股票的历史数据（用于计算指标）
            codes = day_data["code"].unique()
            
            for code in codes:
                # 获取该股票截至当天的所有历史数据
                stock_data = data[
                    (data["code"] == code) & 
                    (data["date"] <= date)
                ].copy()
                
                if len(stock_data) > 0:
                    # 调用策略的on_bar方法
                    try:
                        strategy.on_bar(stock_data)
                    except Exception as e:
                        logger.warning(f"⚠️ 策略执行出错 {code}@{date}: {e}")
            
            # 记录当天的资金曲线
            # 计算当天收盘价
            prices = {}
            for _, row in day_data.iterrows():
                prices[row["code"]] = row["close"]
            
            total_value = strategy.get_total_value(prices)
            equity_curve.append({
                "date": date,
                "value": total_value,
                "cash": strategy.cash,
                "positions": dict(strategy.positions)
            })
        
        return strategy, equity_curve, strategy.trades
    
    def _calculate_metrics(
        self,
        equity_curve: List[Dict],
        trades: List[Dict],
        initial_capital: float,
        commission_rate: float,
        slippage: float
    ) -> Dict[str, Any]:
        """计算回测指标"""
        
        if not equity_curve:
            return self._empty_results(initial_capital)
        
        # 提取资金曲线
        dates = [e["date"] for e in equity_curve]
        values = [e["value"] for e in equity_curve]
        
        final_capital = values[-1]
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100
        
        # 计算最大回撤
        max_drawdown = self._calculate_max_drawdown(values)
        
        # 计算夏普比率
        sharpe_ratio = self._calculate_sharpe_ratio(values)
        
        # 处理交易记录
        processed_trades = self._process_trades(trades, dates, commission_rate, slippage)
        
        # 计算交易统计
        total_trades = len([t for t in processed_trades if t["action"] == "sell"])
        winning_trades = len([t for t in processed_trades if t.get("pnl", 0) > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "initial_capital": initial_capital,
            "final_capital": final_capital,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "equity_curve": {
                "dates": [self._format_date(d) for d in dates],
                "values": values
            },
            "trades": processed_trades[:100]  # 限制返回前100笔交易
        }
    
    def _calculate_max_drawdown(self, values: List[float]) -> float:
        """计算最大回撤"""
        max_dd = 0
        peak = values[0]
        
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _calculate_sharpe_ratio(self, values: List[float]) -> float:
        """计算夏普比率（简化版）"""
        if len(values) < 2:
            return 0
        
        returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # 年化夏普比率（假设252个交易日）
        sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        
        return sharpe
    
    def _process_trades(
        self,
        trades: List[Dict],
        dates: List[str],
        commission_rate: float,
        slippage: float
    ) -> List[Dict]:
        """处理交易记录"""
        processed = []
        buy_prices = {}  # {code: price}
        
        for i, trade in enumerate(trades):
            action = trade["action"]
            code = trade["code"]
            quantity = trade["quantity"]
            price = trade["price"]
            
            # 应用滑点和手续费
            if action == "buy":
                actual_price = price * (1 + slippage)
                commission = actual_price * quantity * commission_rate
                amount = actual_price * quantity + commission
                buy_prices[code] = actual_price
                pnl = None
            else:  # sell
                actual_price = price * (1 - slippage)
                commission = actual_price * quantity * commission_rate
                amount = actual_price * quantity - commission
                
                # 计算盈亏
                if code in buy_prices:
                    buy_price = buy_prices[code]
                    pnl = (actual_price - buy_price) * quantity - commission * 2
                else:
                    pnl = None
            
            # 获取日期（简化：使用索引）
            date_idx = min(i // 2, len(dates) - 1)
            trade_date = dates[date_idx] if date_idx < len(dates) else dates[-1]
            
            processed.append({
                "date": self._format_date(trade_date),
                "action": action,
                "code": code,
                "price": round(price, 2),
                "quantity": quantity,
                "amount": round(amount, 2),
                "pnl": round(pnl, 2) if pnl is not None else None
            })
        
        return processed
    
    def _format_date(self, date_str: str) -> str:
        """格式化日期"""
        if len(date_str) == 8:  # YYYYMMDD
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str
    
    def _empty_results(self, initial_capital: float) -> Dict[str, Any]:
        """空结果"""
        return {
            "initial_capital": initial_capital,
            "final_capital": initial_capital,
            "total_return": 0,
            "total_return_pct": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "total_trades": 0,
            "win_rate": 0,
            "equity_curve": {"dates": [], "values": []},
            "trades": []
        }

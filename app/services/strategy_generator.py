"""
AI策略生成器
使用LLM根据用户的自然语言描述生成交易策略代码
"""
import logging
from typing import Optional
import os

logger = logging.getLogger(__name__)


class StrategyGenerator:
    """AI策略生成器"""
    
    def __init__(self):
        self.llm_service = None
        self._init_llm()
    
    def _init_llm(self):
        """初始化LLM服务"""
        try:
            from app.services.llm_service import LLMService
            self.llm_service = LLMService()
            logger.info("✅ LLM服务初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ LLM服务初始化失败: {e}")
    
    async def generate_strategy(self, prompt: str, market: str) -> str:
        """
        根据用户描述生成策略代码
        
        Args:
            prompt: 用户的策略描述
            market: 市场类型 (CN/TW/HK/US)
        
        Returns:
            Python策略代码
        """
        logger.info(f"🤖 开始生成策略 - 市场: {market}")
        logger.info(f"📝 用户描述: {prompt}")
        
        # 构建系统提示词
        system_prompt = self._build_system_prompt(market)
        
        # 构建用户提示词
        user_prompt = f"""
请根据以下描述生成交易策略代码：

{prompt}

要求：
1. 使用Python编写
2. 包含Strategy类，继承自BaseStrategy
3. 实现on_bar()方法处理K线数据
4. 使用self.buy()和self.sell()进行交易
5. 添加必要的注释
6. 确保代码可以直接运行

请只返回代码，不要包含其他说明文字。
"""
        
        try:
            if self.llm_service:
                # 使用LLM生成
                response = await self.llm_service.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                code = self._extract_code(response)
                logger.info("✅ AI策略生成成功")
                return code
            else:
                # 降级到模板策略
                logger.warning("⚠️ LLM服务不可用，使用模板策略")
                return self._generate_template_strategy(prompt, market)
                
        except Exception as e:
            logger.error(f"❌ 生成策略失败: {e}")
            # 降级到模板策略
            return self._generate_template_strategy(prompt, market)
    
    def _build_system_prompt(self, market: str) -> str:
        """构建系统提示词"""
        market_info = {
            "CN": "A股市场（人民币CNY）",
            "TW": "台股市场（新台币TWD）",
            "HK": "港股市场（港币HKD）",
            "US": "美股市场（美元USD）"
        }
        
        return f"""你是一个专业的量化交易策略开发专家。

目标市场: {market_info.get(market, market)}

你需要根据用户的自然语言描述，生成可执行的Python交易策略代码。

策略框架说明：
```python
class BaseStrategy:
    def __init__(self, initial_capital=1000000):
        self.capital = initial_capital
        self.positions = {{}}  # {{code: quantity}}
        self.cash = initial_capital
        
    def buy(self, code, quantity, price):
        \"\"\"买入股票\"\"\"
        cost = quantity * price
        if cost <= self.cash:
            self.cash -= cost
            self.positions[code] = self.positions.get(code, 0) + quantity
            return True
        return False
    
    def sell(self, code, quantity, price):
        \"\"\"卖出股票\"\"\"
        if self.positions.get(code, 0) >= quantity:
            self.cash += quantity * price
            self.positions[code] -= quantity
            if self.positions[code] == 0:
                del self.positions[code]
            return True
        return False
    
    def on_bar(self, data):
        \"\"\"处理K线数据（需要子类实现）\"\"\"
        pass
```

可用的技术指标库（已导入）：
- pandas: pd
- numpy: np
- talib: ta (包含RSI, MACD, BOLL等)

代码要求：
1. 继承BaseStrategy类
2. 实现on_bar(data)方法
3. data是DataFrame，包含列: date, code, open, high, low, close, volume
4. 使用self.buy()和self.sell()进行交易
5. 可以使用self.cash查询可用资金
6. 可以使用self.positions查询持仓

请生成完整、可运行的策略代码。
"""
    
    def _extract_code(self, response: str) -> str:
        """从LLM响应中提取代码"""
        # 移除markdown代码块标记
        code = response.strip()
        
        if code.startswith("```python"):
            code = code[len("```python"):].strip()
        elif code.startswith("```"):
            code = code[len("```"):].strip()
        
        if code.endswith("```"):
            code = code[:-3].strip()
        
        return code
    
    def _generate_template_strategy(self, prompt: str, market: str) -> str:
        """生成模板策略（降级方案）"""
        logger.info("📝 使用模板策略")
        
        # 分析prompt中的关键词
        is_rsi = "rsi" in prompt.lower() or "相对强弱" in prompt
        is_ma = "均线" in prompt or "ma" in prompt.lower() or "moving average" in prompt.lower()
        is_macd = "macd" in prompt.lower()
        
        if is_rsi:
            return self._generate_rsi_strategy()
        elif is_ma:
            return self._generate_ma_strategy()
        elif is_macd:
            return self._generate_macd_strategy()
        else:
            # 默认策略
            return self._generate_simple_momentum_strategy()
    
    def _generate_rsi_strategy(self) -> str:
        """生成RSI策略"""
        return '''
import pandas as pd
import numpy as np
import talib as ta

class Strategy(BaseStrategy):
    """RSI均值回归策略
    
    策略逻辑：
    - 当RSI < 30时，认为超卖，买入
    - 当RSI > 70时，认为超买，卖出
    - 每次交易使用可用资金的20%
    """
    
    def __init__(self, initial_capital=1000000):
        super().__init__(initial_capital)
        self.rsi_period = 14
        self.oversold = 30
        self.overbought = 70
        self.position_size = 0.2  # 每次使用20%资金
    
    def on_bar(self, data):
        """处理每根K线数据"""
        # 至少需要rsi_period+1根K线才能计算RSI
        if len(data) < self.rsi_period + 1:
            return
        
        # 计算RSI
        close_prices = data['close'].values
        rsi = ta.RSI(close_prices, timeperiod=self.rsi_period)
        current_rsi = rsi[-1]
        
        # 获取当前价格和代码
        current_bar = data.iloc[-1]
        code = current_bar['code']
        price = current_bar['close']
        
        # 检查是否为NaN
        if pd.isna(current_rsi):
            return
        
        # 买入信号：RSI < 30（超卖）
        if current_rsi < self.oversold:
            if code not in self.positions:
                # 计算可买入数量
                available_cash = self.cash * self.position_size
                quantity = int(available_cash / price / 100) * 100  # 买入整百股
                
                if quantity > 0:
                    success = self.buy(code, quantity, price)
                    if success:
                        print(f"[买入] {code} 数量:{quantity} 价格:{price:.2f} RSI:{current_rsi:.2f}")
        
        # 卖出信号：RSI > 70（超买）
        elif current_rsi > self.overbought:
            if code in self.positions:
                quantity = self.positions[code]
                success = self.sell(code, quantity, price)
                if success:
                    print(f"[卖出] {code} 数量:{quantity} 价格:{price:.2f} RSI:{current_rsi:.2f}")
'''
    
    def _generate_ma_strategy(self) -> str:
        """生成均线策略"""
        return '''
import pandas as pd
import numpy as np
import talib as ta

class Strategy(BaseStrategy):
    """双均线策略
    
    策略逻辑：
    - 短期均线上穿长期均线（金叉）时买入
    - 短期均线下穿长期均线（死叉）时卖出
    """
    
    def __init__(self, initial_capital=1000000):
        super().__init__(initial_capital)
        self.short_period = 5
        self.long_period = 20
        self.position_size = 0.3  # 每次使用30%资金
    
    def on_bar(self, data):
        """处理每根K线数据"""
        # 至少需要long_period根K线
        if len(data) < self.long_period:
            return
        
        # 计算均线
        close_prices = data['close'].values
        ma_short = ta.SMA(close_prices, timeperiod=self.short_period)
        ma_long = ta.SMA(close_prices, timeperiod=self.long_period)
        
        # 获取当前和前一根K线的均线值
        current_short = ma_short[-1]
        current_long = ma_long[-1]
        prev_short = ma_short[-2]
        prev_long = ma_long[-2]
        
        # 获取当前价格和代码
        current_bar = data.iloc[-1]
        code = current_bar['code']
        price = current_bar['close']
        
        # 检查是否为NaN
        if pd.isna(current_short) or pd.isna(current_long):
            return
        
        # 金叉买入：短期均线上穿长期均线
        if prev_short <= prev_long and current_short > current_long:
            if code not in self.positions:
                available_cash = self.cash * self.position_size
                quantity = int(available_cash / price / 100) * 100
                
                if quantity > 0:
                    success = self.buy(code, quantity, price)
                    if success:
                        print(f"[金叉买入] {code} 数量:{quantity} 价格:{price:.2f}")
        
        # 死叉卖出：短期均线下穿长期均线
        elif prev_short >= prev_long and current_short < current_long:
            if code in self.positions:
                quantity = self.positions[code]
                success = self.sell(code, quantity, price)
                if success:
                    print(f"[死叉卖出] {code} 数量:{quantity} 价格:{price:.2f}")
'''
    
    def _generate_macd_strategy(self) -> str:
        """生成MACD策略"""
        return '''
import pandas as pd
import numpy as np
import talib as ta

class Strategy(BaseStrategy):
    """MACD策略
    
    策略逻辑：
    - MACD线上穿信号线（金叉）时买入
    - MACD线下穿信号线（死叉）时卖出
    """
    
    def __init__(self, initial_capital=1000000):
        super().__init__(initial_capital)
        self.fast_period = 12
        self.slow_period = 26
        self.signal_period = 9
        self.position_size = 0.25
    
    def on_bar(self, data):
        """处理每根K线数据"""
        if len(data) < self.slow_period + self.signal_period:
            return
        
        # 计算MACD
        close_prices = data['close'].values
        macd, signal, hist = ta.MACD(
            close_prices,
            fastperiod=self.fast_period,
            slowperiod=self.slow_period,
            signalperiod=self.signal_period
        )
        
        # 获取当前和前一根K线的MACD值
        current_macd = macd[-1]
        current_signal = signal[-1]
        prev_macd = macd[-2]
        prev_signal = signal[-2]
        
        current_bar = data.iloc[-1]
        code = current_bar['code']
        price = current_bar['close']
        
        if pd.isna(current_macd) or pd.isna(current_signal):
            return
        
        # 金叉买入
        if prev_macd <= prev_signal and current_macd > current_signal:
            if code not in self.positions:
                available_cash = self.cash * self.position_size
                quantity = int(available_cash / price / 100) * 100
                
                if quantity > 0:
                    success = self.buy(code, quantity, price)
                    if success:
                        print(f"[MACD金叉] {code} 数量:{quantity} 价格:{price:.2f}")
        
        # 死叉卖出
        elif prev_macd >= prev_signal and current_macd < current_signal:
            if code in self.positions:
                quantity = self.positions[code]
                success = self.sell(code, quantity, price)
                if success:
                    print(f"[MACD死叉] {code} 数量:{quantity} 价格:{price:.2f}")
'''
    
    def _generate_simple_momentum_strategy(self) -> str:
        """生成简单动量策略"""
        return '''
import pandas as pd
import numpy as np

class Strategy(BaseStrategy):
    """简单动量策略
    
    策略逻辑：
    - 计算过去N天的收益率
    - 收益率为正且大于阈值时买入
    - 持有K天或收益率转负时卖出
    """
    
    def __init__(self, initial_capital=1000000):
        super().__init__(initial_capital)
        self.lookback_period = 20  # 回看周期
        self.holding_period = 10   # 持有周期
        self.entry_threshold = 0.05  # 进入阈值5%
        self.position_size = 0.3
        self.entry_dates = {}  # 记录买入日期
    
    def on_bar(self, data):
        """处理每根K线数据"""
        if len(data) < self.lookback_period:
            return
        
        current_bar = data.iloc[-1]
        code = current_bar['code']
        price = current_bar['close']
        current_date = current_bar['date']
        
        # 计算动量（过去N天收益率）
        past_price = data.iloc[-self.lookback_period]['close']
        momentum = (price - past_price) / past_price
        
        # 买入信号
        if momentum > self.entry_threshold:
            if code not in self.positions:
                available_cash = self.cash * self.position_size
                quantity = int(available_cash / price / 100) * 100
                
                if quantity > 0:
                    success = self.buy(code, quantity, price)
                    if success:
                        self.entry_dates[code] = current_date
                        print(f"[买入] {code} 数量:{quantity} 价格:{price:.2f} 动量:{momentum:.2%}")
        
        # 卖出信号
        elif code in self.positions:
            # 持有超过holding_period天或动量转负
            if (code in self.entry_dates and 
                (current_date - self.entry_dates[code]).days >= self.holding_period) or \
               momentum < 0:
                quantity = self.positions[code]
                success = self.sell(code, quantity, price)
                if success:
                    if code in self.entry_dates:
                        del self.entry_dates[code]
                    print(f"[卖出] {code} 数量:{quantity} 价格:{price:.2f}")
'''


# 基础策略类定义（回测引擎会使用）
BASE_STRATEGY_CLASS = '''
class BaseStrategy:
    """策略基类"""
    
    def __init__(self, initial_capital=1000000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}  # {code: quantity}
        self.cash = initial_capital
        self.trades = []
        
    def buy(self, code, quantity, price):
        """买入股票"""
        cost = quantity * price
        if cost <= self.cash:
            self.cash -= cost
            self.positions[code] = self.positions.get(code, 0) + quantity
            self.trades.append({
                'action': 'buy',
                'code': code,
                'quantity': quantity,
                'price': price,
                'cost': cost
            })
            return True
        return False
    
    def sell(self, code, quantity, price):
        """卖出股票"""
        if self.positions.get(code, 0) >= quantity:
            revenue = quantity * price
            self.cash += revenue
            self.positions[code] -= quantity
            if self.positions[code] == 0:
                del self.positions[code]
            self.trades.append({
                'action': 'sell',
                'code': code,
                'quantity': quantity,
                'price': price,
                'revenue': revenue
            })
            return True
        return False
    
    def get_position_value(self, prices):
        """计算持仓市值"""
        total = 0
        for code, quantity in self.positions.items():
            if code in prices:
                total += quantity * prices[code]
        return total
    
    def get_total_value(self, prices):
        """计算总资产"""
        return self.cash + self.get_position_value(prices)
    
    def on_bar(self, data):
        """处理K线数据（需要子类实现）"""
        raise NotImplementedError("子类必须实现on_bar方法")
'''

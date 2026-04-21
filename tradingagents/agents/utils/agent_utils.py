from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage, AIMessage
from typing import List
from typing import Annotated
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import RemoveMessage
from langchain_core.tools import tool
from datetime import date, timedelta, datetime
import functools
import pandas as pd
import os
from dateutil.relativedelta import relativedelta
from langchain_openai import ChatOpenAI
import tradingagents.dataflows.interface as interface
from tradingagents.default_config import DEFAULT_CONFIG
from langchain_core.messages import HumanMessage

# 导入统一日志系统和工具日志装饰器
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_tool_call, log_analysis_step

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]
        
        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]
        
        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")
        
        return {"messages": removal_operations + [placeholder]}
    
    return delete_messages


class Toolkit:
    _config = DEFAULT_CONFIG.copy()

    @classmethod
    def update_config(cls, config):
        """Update the class-level configuration."""
        cls._config.update(config)

    @property
    def config(self):
        """Access the configuration."""
        return self._config

    def __init__(self, config=None):
        if config:
            self.update_config(config)

    @staticmethod
    @tool
    def get_reddit_news(
        curr_date: Annotated[str, "Date you want to get news for in yyyy-mm-dd format"],
    ) -> str:
        """
        Retrieve global news from Reddit within a specified time frame.
        Args:
            curr_date (str): Date you want to get news for in yyyy-mm-dd format
        Returns:
            str: A formatted dataframe containing the latest global news from Reddit in the specified time frame.
        """
        
        global_news_result = interface.get_reddit_global_news(curr_date, 7, 5)

        return global_news_result

    @staticmethod
    @tool
    def get_finnhub_news(
        ticker: Annotated[
            str,
            "Search query of a company, e.g. 'AAPL, TSM, etc.",
        ],
        start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
        end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest news about a given stock from Finnhub within a date range
        Args:
            ticker (str): Ticker of a company. e.g. AAPL, TSM
            start_date (str): Start date in yyyy-mm-dd format
            end_date (str): End date in yyyy-mm-dd format
        Returns:
            str: A formatted dataframe containing news about the company within the date range from start_date to end_date
        """

        end_date_str = end_date

        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        look_back_days = (end_date - start_date).days

        finnhub_news_result = interface.get_finnhub_news(
            ticker, end_date_str, look_back_days
        )

        return finnhub_news_result

    @staticmethod
    @tool
    def get_reddit_stock_info(
        ticker: Annotated[
            str,
            "Ticker of a company. e.g. AAPL, TSM",
        ],
        curr_date: Annotated[str, "Current date you want to get news for"],
    ) -> str:
        """
        Retrieve the latest news about a given stock from Reddit, given the current date.
        Args:
            ticker (str): Ticker of a company. e.g. AAPL, TSM
            curr_date (str): current date in yyyy-mm-dd format to get news for
        Returns:
            str: A formatted dataframe containing the latest news about the company on the given date
        """

        stock_news_results = interface.get_reddit_company_news(ticker, curr_date, 7, 5)

        return stock_news_results

    @staticmethod
    @tool
    def get_chinese_social_sentiment(
        ticker: Annotated[str, "Ticker of a company. e.g. AAPL, TSM"],
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ) -> str:
        """
        获取中国社交媒体和财经平台上关于特定股票的情绪分析和讨论热度。
        整合雪球、东方财富股吧、新浪财经等中国本土平台的数据。
        Args:
            ticker (str): 股票代码，如 AAPL, TSM
            curr_date (str): 当前日期，格式为 yyyy-mm-dd
        Returns:
            str: 包含中国投资者情绪分析、讨论热度、关键观点的格式化报告
        """
        try:
            # 这里可以集成多个中国平台的数据
            chinese_sentiment_results = interface.get_chinese_social_sentiment(ticker, curr_date)
            return chinese_sentiment_results
        except Exception as e:
            # 如果中国平台数据获取失败，回退到原有的Reddit数据
            return interface.get_reddit_company_news(ticker, curr_date, 7, 5)

    @staticmethod
    # @tool  # 已移除：请使用 get_stock_fundamentals_unified 或 get_stock_market_data_unified
    def get_china_stock_data(
        stock_code: Annotated[str, "中国股票代码，如 000001(平安银行), 600519(贵州茅台)"],
        start_date: Annotated[str, "开始日期，格式 yyyy-mm-dd"],
        end_date: Annotated[str, "结束日期，格式 yyyy-mm-dd"],
    ) -> str:
        """
        获取中国A股实时和历史数据，通过Tushare等高质量数据源提供专业的股票数据。
        支持实时行情、历史K线、技术指标等全面数据，自动使用最佳数据源。
        Args:
            stock_code (str): 中国股票代码，如 000001(平安银行), 600519(贵州茅台)
            start_date (str): 开始日期，格式 yyyy-mm-dd
            end_date (str): 结束日期，格式 yyyy-mm-dd
        Returns:
            str: 包含实时行情、历史数据、技术指标的完整股票分析报告
        """
        try:
            logger.debug(f"📊 [DEBUG] ===== agent_utils.get_china_stock_data 开始调用 =====")
            logger.debug(f"📊 [DEBUG] 参数: stock_code={stock_code}, start_date={start_date}, end_date={end_date}")

            from tradingagents.dataflows.interface import get_china_stock_data_unified
            logger.debug(f"📊 [DEBUG] 成功导入统一数据源接口")

            logger.debug(f"📊 [DEBUG] 正在调用统一数据源接口...")
            result = get_china_stock_data_unified(stock_code, start_date, end_date)

            logger.debug(f"📊 [DEBUG] 统一数据源接口调用完成")
            logger.debug(f"📊 [DEBUG] 返回结果类型: {type(result)}")
            logger.debug(f"📊 [DEBUG] 返回结果长度: {len(result) if result else 0}")
            logger.debug(f"📊 [DEBUG] 返回结果前200字符: {str(result)[:200]}...")
            logger.debug(f"📊 [DEBUG] ===== agent_utils.get_china_stock_data 调用结束 =====")

            return result
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"❌ [DEBUG] ===== agent_utils.get_china_stock_data 异常 =====")
            logger.error(f"❌ [DEBUG] 错误类型: {type(e).__name__}")
            logger.error(f"❌ [DEBUG] 错误信息: {str(e)}")
            logger.error(f"❌ [DEBUG] 详细堆栈:")
            print(error_details)
            logger.error(f"❌ [DEBUG] ===== 异常处理结束 =====")
            return f"中国股票数据获取失败: {str(e)}。请检查网络连接或稍后重试。"

    @staticmethod
    @tool
    def get_china_market_overview(
        curr_date: Annotated[str, "当前日期，格式 yyyy-mm-dd"],
    ) -> str:
        """
        获取中国股市整体概览，包括主要指数的实时行情。
        涵盖上证指数、深证成指、创业板指、科创50等主要指数。
        Args:
            curr_date (str): 当前日期，格式 yyyy-mm-dd
        Returns:
            str: 包含主要指数实时行情的市场概览报告
        """
        try:
            # 使用Tushare获取主要指数数据
            from tradingagents.dataflows.providers.china.tushare import get_tushare_adapter

            adapter = get_tushare_adapter()


            # 使用Tushare获取主要指数信息
            # 这里可以扩展为获取具体的指数数据
            return f"""# 中国股市概览 - {curr_date}

## 📊 主要指数
- 上证指数: 数据获取中...
- 深证成指: 数据获取中...
- 创业板指: 数据获取中...
- 科创50: 数据获取中...

## 💡 说明
市场概览功能正在从TDX迁移到Tushare，完整功能即将推出。
当前可以使用股票数据获取功能分析个股。

数据来源: Tushare专业数据源
更新时间: {curr_date}
"""

        except Exception as e:
            return f"中国市场概览获取失败: {str(e)}。正在从TDX迁移到Tushare数据源。"

    @staticmethod
    @tool
    def get_YFin_data(
        symbol: Annotated[str, "ticker symbol of the company"],
        start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
        end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    ) -> str:
        """
        Retrieve the stock price data for a given ticker symbol from Yahoo Finance.
        Args:
            symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
            start_date (str): Start date in yyyy-mm-dd format
            end_date (str): End date in yyyy-mm-dd format
        Returns:
            str: A formatted dataframe containing the stock price data for the specified ticker symbol in the specified date range.
        """

        result_data = interface.get_YFin_data(symbol, start_date, end_date)

        return result_data

    @staticmethod
    @tool
    def get_YFin_data_online(
        symbol: Annotated[str, "ticker symbol of the company"],
        start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
        end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    ) -> str:
        """
        Retrieve the stock price data for a given ticker symbol from Yahoo Finance.
        Args:
            symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
            start_date (str): Start date in yyyy-mm-dd format
            end_date (str): End date in yyyy-mm-dd format
        Returns:
            str: A formatted dataframe containing the stock price data for the specified ticker symbol in the specified date range.
        """

        result_data = interface.get_YFin_data_online(symbol, start_date, end_date)

        return result_data

    @staticmethod
    @tool
    def get_stockstats_indicators_report(
        symbol: Annotated[str, "ticker symbol of the company"],
        indicator: Annotated[
            str, "technical indicator to get the analysis and report of"
        ],
        curr_date: Annotated[
            str, "The current trading date you are trading on, YYYY-mm-dd"
        ],
        look_back_days: Annotated[int, "how many days to look back"] = 30,
    ) -> str:
        """
        Retrieve stock stats indicators for a given ticker symbol and indicator.
        Args:
            symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
            indicator (str): Technical indicator to get the analysis and report of
            curr_date (str): The current trading date you are trading on, YYYY-mm-dd
            look_back_days (int): How many days to look back, default is 30
        Returns:
            str: A formatted dataframe containing the stock stats indicators for the specified ticker symbol and indicator.
        """

        result_stockstats = interface.get_stock_stats_indicators_window(
            symbol, indicator, curr_date, look_back_days, False
        )

        return result_stockstats

    @staticmethod
    @tool
    def get_stockstats_indicators_report_online(
        symbol: Annotated[str, "ticker symbol of the company"],
        indicator: Annotated[
            str, "technical indicator to get the analysis and report of"
        ],
        curr_date: Annotated[
            str, "The current trading date you are trading on, YYYY-mm-dd"
        ],
        look_back_days: Annotated[int, "how many days to look back"] = 30,
    ) -> str:
        """
        Retrieve stock stats indicators for a given ticker symbol and indicator.
        Args:
            symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
            indicator (str): Technical indicator to get the analysis and report of
            curr_date (str): The current trading date you are trading on, YYYY-mm-dd
            look_back_days (int): How many days to look back, default is 30
        Returns:
            str: A formatted dataframe containing the stock stats indicators for the specified ticker symbol and indicator.
        """

        result_stockstats = interface.get_stock_stats_indicators_window(
            symbol, indicator, curr_date, look_back_days, True
        )

        return result_stockstats

    @staticmethod
    @tool
    def get_finnhub_company_insider_sentiment(
        ticker: Annotated[str, "ticker symbol for the company"],
        curr_date: Annotated[
            str,
            "current date of you are trading at, yyyy-mm-dd",
        ],
    ):
        """
        Retrieve insider sentiment information about a company (retrieved from public SEC information) for the past 30 days
        Args:
            ticker (str): ticker symbol of the company
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
            str: a report of the sentiment in the past 30 days starting at curr_date
        """

        data_sentiment = interface.get_finnhub_company_insider_sentiment(
            ticker, curr_date, 30
        )

        return data_sentiment

    @staticmethod
    @tool
    def get_finnhub_company_insider_transactions(
        ticker: Annotated[str, "ticker symbol"],
        curr_date: Annotated[
            str,
            "current date you are trading at, yyyy-mm-dd",
        ],
    ):
        """
        Retrieve insider transaction information about a company (retrieved from public SEC information) for the past 30 days
        Args:
            ticker (str): ticker symbol of the company
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
            str: a report of the company's insider transactions/trading information in the past 30 days
        """

        data_trans = interface.get_finnhub_company_insider_transactions(
            ticker, curr_date, 30
        )

        return data_trans

    @staticmethod
    @tool
    def get_simfin_balance_sheet(
        ticker: Annotated[str, "ticker symbol"],
        freq: Annotated[
            str,
            "reporting frequency of the company's financial history: annual/quarterly",
        ],
        curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    ):
        """
        Retrieve the most recent balance sheet of a company
        Args:
            ticker (str): ticker symbol of the company
            freq (str): reporting frequency of the company's financial history: annual / quarterly
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
            str: a report of the company's most recent balance sheet
        """

        data_balance_sheet = interface.get_simfin_balance_sheet(ticker, freq, curr_date)

        return data_balance_sheet

    @staticmethod
    @tool
    def get_simfin_cashflow(
        ticker: Annotated[str, "ticker symbol"],
        freq: Annotated[
            str,
            "reporting frequency of the company's financial history: annual/quarterly",
        ],
        curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    ):
        """
        Retrieve the most recent cash flow statement of a company
        Args:
            ticker (str): ticker symbol of the company
            freq (str): reporting frequency of the company's financial history: annual / quarterly
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
                str: a report of the company's most recent cash flow statement
        """

        data_cashflow = interface.get_simfin_cashflow(ticker, freq, curr_date)

        return data_cashflow

    @staticmethod
    @tool
    def get_simfin_income_stmt(
        ticker: Annotated[str, "ticker symbol"],
        freq: Annotated[
            str,
            "reporting frequency of the company's financial history: annual/quarterly",
        ],
        curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    ):
        """
        Retrieve the most recent income statement of a company
        Args:
            ticker (str): ticker symbol of the company
            freq (str): reporting frequency of the company's financial history: annual / quarterly
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
                str: a report of the company's most recent income statement
        """

        data_income_stmt = interface.get_simfin_income_statements(
            ticker, freq, curr_date
        )

        return data_income_stmt

    @staticmethod
    @tool
    def get_google_news(
        query: Annotated[str, "Query to search with"],
        curr_date: Annotated[str, "Curr date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest news from Google News based on a query and date range.
        Args:
            query (str): Query to search with
            curr_date (str): Current date in yyyy-mm-dd format
            look_back_days (int): How many days to look back
        Returns:
            str: A formatted string containing the latest news from Google News based on the query and date range.
        """

        google_news_results = interface.get_google_news(query, curr_date, 7)

        return google_news_results

    @staticmethod
    @tool
    def get_realtime_stock_news(
        ticker: Annotated[str, "Ticker of a company. e.g. AAPL, TSM"],
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ) -> str:
        """
        获取股票的实时新闻分析，解决传统新闻源的滞后性问题。
        整合多个专业财经API，提供15-30分钟内的最新新闻。
        支持多种新闻源轮询机制，优先使用实时新闻聚合器，失败时自动尝试备用新闻源。
        对于A股和港股，会优先使用中文财经新闻源（如东方财富）。
        
        Args:
            ticker (str): 股票代码，如 AAPL, TSM, 600036.SH
            curr_date (str): 当前日期，格式为 yyyy-mm-dd
        Returns:
            str: 包含实时新闻分析、紧急程度评估、时效性说明的格式化报告
        """
        from tradingagents.dataflows.realtime_news_utils import get_realtime_stock_news
        return get_realtime_stock_news(ticker, curr_date, hours_back=6)

    @staticmethod
    @tool
    def get_stock_news_openai(
        ticker: Annotated[str, "the company's ticker"],
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest news about a given stock by using OpenAI's news API.
        Args:
            ticker (str): Ticker of a company. e.g. AAPL, TSM
            curr_date (str): Current date in yyyy-mm-dd format
        Returns:
            str: A formatted string containing the latest news about the company on the given date.
        """

        openai_news_results = interface.get_stock_news_openai(ticker, curr_date)

        return openai_news_results

    @staticmethod
    @tool
    def get_global_news_openai(
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest macroeconomics news on a given date using OpenAI's macroeconomics news API.
        Args:
            curr_date (str): Current date in yyyy-mm-dd format
        Returns:
            str: A formatted string containing the latest macroeconomic news on the given date.
        """

        openai_news_results = interface.get_global_news_openai(curr_date)

        return openai_news_results

    @staticmethod
    # @tool  # 已移除：请使用 get_stock_fundamentals_unified
    def get_fundamentals_openai(
        ticker: Annotated[str, "the company's ticker"],
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest fundamental information about a given stock on a given date by using OpenAI's news API.
        Args:
            ticker (str): Ticker of a company. e.g. AAPL, TSM
            curr_date (str): Current date in yyyy-mm-dd format
        Returns:
            str: A formatted string containing the latest fundamental information about the company on the given date.
        """
        logger.debug(f"📊 [DEBUG] get_fundamentals_openai 被调用: ticker={ticker}, date={curr_date}")

        # 检查是否为中国股票
        import re
        if re.match(r'^\d{6}$', str(ticker)):
            logger.debug(f"📊 [DEBUG] 检测到中国A股代码: {ticker}")
            # 使用统一接口获取中国股票名称
            try:
                from tradingagents.dataflows.interface import get_china_stock_info_unified
                stock_info = get_china_stock_info_unified(ticker)

                # 解析股票名称
                if "股票名称:" in stock_info:
                    company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                else:
                    company_name = f"股票代码{ticker}"

                logger.debug(f"📊 [DEBUG] 中国股票名称映射: {ticker} -> {company_name}")
            except Exception as e:
                logger.error(f"⚠️ [DEBUG] 从统一接口获取股票名称失败: {e}")
                company_name = f"股票代码{ticker}"

            # 修改查询以包含正确的公司名称
            modified_query = f"{company_name}({ticker})"
            logger.debug(f"📊 [DEBUG] 修改后的查询: {modified_query}")
        else:
            logger.debug(f"📊 [DEBUG] 检测到非中国股票: {ticker}")
            modified_query = ticker

        try:
            openai_fundamentals_results = interface.get_fundamentals_openai(
                modified_query, curr_date
            )
            logger.debug(f"📊 [DEBUG] OpenAI基本面分析结果长度: {len(openai_fundamentals_results) if openai_fundamentals_results else 0}")
            return openai_fundamentals_results
        except Exception as e:
            logger.error(f"❌ [DEBUG] OpenAI基本面分析失败: {str(e)}")
            return f"基本面分析失败: {str(e)}"

    @staticmethod
    # @tool  # 已移除：请使用 get_stock_fundamentals_unified
    def get_china_fundamentals(
        ticker: Annotated[str, "中国A股股票代码，如600036"],
        curr_date: Annotated[str, "当前日期，格式为yyyy-mm-dd"],
    ):
        """
        获取中国A股股票的基本面信息，使用中国股票数据源。
        Args:
            ticker (str): 中国A股股票代码，如600036, 000001
            curr_date (str): 当前日期，格式为yyyy-mm-dd
        Returns:
            str: 包含股票基本面信息的格式化字符串
        """
        logger.debug(f"📊 [DEBUG] get_china_fundamentals 被调用: ticker={ticker}, date={curr_date}")

        # 检查是否为中国股票
        import re
        if not re.match(r'^\d{6}$', str(ticker)):
            return f"错误：{ticker} 不是有效的中国A股代码格式"

        try:
            # 使用统一数据源接口获取股票数据（默认Tushare，支持备用数据源）
            from tradingagents.dataflows.interface import get_china_stock_data_unified
            logger.debug(f"📊 [DEBUG] 正在获取 {ticker} 的股票数据...")

            # 获取最近30天的数据用于基本面分析
            from datetime import datetime, timedelta
            end_date = datetime.strptime(curr_date, '%Y-%m-%d')
            start_date = end_date - timedelta(days=30)

            stock_data = get_china_stock_data_unified(
                ticker,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )

            logger.debug(f"📊 [DEBUG] 股票数据获取完成，长度: {len(stock_data) if stock_data else 0}")

            if not stock_data or "获取失败" in stock_data or "❌" in stock_data:
                return f"无法获取股票 {ticker} 的基本面数据：{stock_data}"

            # 调用真正的基本面分析
            from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider

            # 创建分析器实例
            analyzer = OptimizedChinaDataProvider()

            # 生成真正的基本面分析报告
            fundamentals_report = analyzer._generate_fundamentals_report(ticker, stock_data)

            logger.debug(f"📊 [DEBUG] 中国基本面分析报告生成完成")
            logger.debug(f"📊 [DEBUG] get_china_fundamentals 结果长度: {len(fundamentals_report)}")

            return fundamentals_report

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"❌ [DEBUG] get_china_fundamentals 失败:")
            logger.error(f"❌ [DEBUG] 错误: {str(e)}")
            logger.error(f"❌ [DEBUG] 堆栈: {error_details}")
            return f"中国股票基本面分析失败: {str(e)}"

    @staticmethod
    # @tool  # 已移除：请使用 get_stock_fundamentals_unified 或 get_stock_market_data_unified
    def get_hk_stock_data_unified(
        symbol: Annotated[str, "港股代码，如：0700.HK、9988.HK等"],
        start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD"],
        end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD"]
    ) -> str:
        """
        获取港股数据的统一接口，优先使用AKShare数据源，备用Yahoo Finance

        Args:
            symbol: 港股代码 (如: 0700.HK)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            str: 格式化的港股数据
        """
        logger.debug(f"🇭🇰 [DEBUG] get_hk_stock_data_unified 被调用: symbol={symbol}, start_date={start_date}, end_date={end_date}")

        try:
            from tradingagents.dataflows.interface import get_hk_stock_data_unified

            result = get_hk_stock_data_unified(symbol, start_date, end_date)

            logger.debug(f"🇭🇰 [DEBUG] 港股数据获取完成，长度: {len(result) if result else 0}")

            return result

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"❌ [DEBUG] get_hk_stock_data_unified 失败:")
            logger.error(f"❌ [DEBUG] 错误: {str(e)}")
            logger.error(f"❌ [DEBUG] 堆栈: {error_details}")
            return f"港股数据获取失败: {str(e)}"

    @staticmethod
    @tool
    @log_tool_call(tool_name="get_stock_fundamentals_unified", log_args=True)
    def get_stock_fundamentals_unified(
        ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
        start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD"] = None,
        end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD"] = None,
        curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"] = None
    ) -> str:
        """
        统一的股票基本面分析工具
        自动识别股票类型（A股、港股、美股）并调用相应的数据源
        支持基于分析级别的数据获取策略

        Args:
            ticker: 股票代码（如：000001、0700.HK、AAPL）
            start_date: 开始日期（可选，格式：YYYY-MM-DD）
            end_date: 结束日期（可选，格式：YYYY-MM-DD）
            curr_date: 当前日期（可选，格式：YYYY-MM-DD）

        Returns:
            str: 基本面分析数据和报告
        """
        logger.info(f"📊 [统一基本面工具] 分析股票: {ticker}")

        # 🔧 获取分析级别配置，支持基于级别的数据获取策略
        research_depth = Toolkit._config.get('research_depth', '标准')
        logger.info(f"🔧 [分析级别] 当前分析级别: {research_depth}")
        
        # 数字等级到中文等级的映射
        numeric_to_chinese = {
            1: "快速",
            2: "基础", 
            3: "标准",
            4: "深度",
            5: "全面"
        }
        
        # 标准化研究深度：支持数字输入
        if isinstance(research_depth, (int, float)):
            research_depth = int(research_depth)
            if research_depth in numeric_to_chinese:
                chinese_depth = numeric_to_chinese[research_depth]
                logger.info(f"🔢 [等级转换] 数字等级 {research_depth} → 中文等级 '{chinese_depth}'")
                research_depth = chinese_depth
            else:
                logger.warning(f"⚠️ 无效的数字等级: {research_depth}，使用默认标准分析")
                research_depth = "标准"
        elif isinstance(research_depth, str):
            # 如果是字符串形式的数字，转换为整数
            if research_depth.isdigit():
                numeric_level = int(research_depth)
                if numeric_level in numeric_to_chinese:
                    chinese_depth = numeric_to_chinese[numeric_level]
                    logger.info(f"🔢 [等级转换] 字符串数字 '{research_depth}' → 中文等级 '{chinese_depth}'")
                    research_depth = chinese_depth
                else:
                    logger.warning(f"⚠️ 无效的字符串数字等级: {research_depth}，使用默认标准分析")
                    research_depth = "标准"
            # 如果已经是中文等级，直接使用
            elif research_depth in ["快速", "基础", "标准", "深度", "全面"]:
                logger.info(f"📝 [等级确认] 使用中文等级: '{research_depth}'")
            else:
                logger.warning(f"⚠️ 未知的研究深度: {research_depth}，使用默认标准分析")
                research_depth = "标准"
        else:
            logger.warning(f"⚠️ 无效的研究深度类型: {type(research_depth)}，使用默认标准分析")
            research_depth = "标准"
        
        # 根据分析级别调整数据获取策略
        # 🔧 修正映射关系：data_depth 应该与 research_depth 保持一致
        if research_depth == "快速":
            # 快速分析：获取基础数据，减少数据源调用
            data_depth = "basic"
            logger.info(f"🔧 [分析级别] 快速分析模式：获取基础数据")
        elif research_depth == "基础":
            # 基础分析：获取标准数据
            data_depth = "standard"
            logger.info(f"🔧 [分析级别] 基础分析模式：获取标准数据")
        elif research_depth == "标准":
            # 标准分析：获取标准数据（不是full！）
            data_depth = "standard"
            logger.info(f"🔧 [分析级别] 标准分析模式：获取标准数据")
        elif research_depth == "深度":
            # 深度分析：获取完整数据
            data_depth = "full"
            logger.info(f"🔧 [分析级别] 深度分析模式：获取完整数据")
        elif research_depth == "全面":
            # 全面分析：获取最全面的数据，包含所有可用数据源
            data_depth = "comprehensive"
            logger.info(f"🔧 [分析级别] 全面分析模式：获取最全面数据")
        else:
            # 默认使用标准分析
            data_depth = "standard"
            logger.info(f"🔧 [分析级别] 未知级别，使用标准分析模式")

        # 添加详细的股票代码追踪日志
        logger.info(f"🔍 [股票代码追踪] 统一基本面工具接收到的原始股票代码: '{ticker}' (类型: {type(ticker)})")
        logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(ticker))}")
        logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(ticker))}")

        # 保存原始ticker用于对比
        original_ticker = ticker

        try:
            from tradingagents.utils.stock_utils import StockUtils
            from datetime import datetime, timedelta

            # 自动识别股票类型
            market_info = StockUtils.get_market_info(ticker)
            is_china = market_info['is_china']
            is_hk = market_info['is_hk']
            is_us = market_info['is_us']

            logger.info(f"🔍 [股票代码追踪] StockUtils.get_market_info 返回的市场信息: {market_info}")
            logger.info(f"📊 [统一基本面工具] 股票类型: {market_info['market_name']}")
            logger.info(f"📊 [统一基本面工具] 货币: {market_info['currency_name']} ({market_info['currency_symbol']})")

            # 检查ticker是否在处理过程中发生了变化
            if str(ticker) != str(original_ticker):
                logger.warning(f"🔍 [股票代码追踪] 警告：股票代码发生了变化！原始: '{original_ticker}' -> 当前: '{ticker}'")

            # 设置默认日期
            if not curr_date:
                curr_date = datetime.now().strftime('%Y-%m-%d')
        
            # 基本面分析优化：不需要大量历史数据，只需要当前价格和财务数据
            # 根据数据深度级别设置不同的分析模块数量，而非历史数据范围
            # 🔧 修正映射关系：analysis_modules 应该与 data_depth 保持一致
            if data_depth == "basic":  # 快速分析：基础模块
                analysis_modules = "basic"
                logger.info(f"📊 [基本面策略] 快速分析模式：获取基础财务指标")
            elif data_depth == "standard":  # 基础/标准分析：标准模块
                analysis_modules = "standard"
                logger.info(f"📊 [基本面策略] 标准分析模式：获取标准财务分析")
            elif data_depth == "full":  # 深度分析：完整模块
                analysis_modules = "full"
                logger.info(f"📊 [基本面策略] 深度分析模式：获取完整基本面分析")
            elif data_depth == "comprehensive":  # 全面分析：综合模块
                analysis_modules = "comprehensive"
                logger.info(f"📊 [基本面策略] 全面分析模式：获取综合基本面分析")
            else:
                analysis_modules = "standard"  # 默认标准分析
                logger.info(f"📊 [基本面策略] 默认模式：获取标准基本面分析")
            
            # 基本面分析策略：
            # 1. 获取10天数据（保证能拿到数据，处理周末/节假日）
            # 2. 只使用最近2天数据参与分析（仅需当前价格）
            days_to_fetch = 10  # 固定获取10天数据
            days_to_analyze = 2  # 只分析最近2天

            logger.info(f"📅 [基本面策略] 获取{days_to_fetch}天数据，分析最近{days_to_analyze}天")

            if not start_date:
                start_date = (datetime.now() - timedelta(days=days_to_fetch)).strftime('%Y-%m-%d')

            if not end_date:
                end_date = curr_date

            result_data = []

            if is_china:
                # 中国A股：基本面分析优化策略 - 只获取必要的当前价格和基本面数据
                logger.info(f"🇨🇳 [统一基本面工具] 处理A股数据，数据深度: {data_depth}...")
                logger.info(f"🔍 [股票代码追踪] 进入A股处理分支，ticker: '{ticker}'")
                logger.info(f"💡 [优化策略] 基本面分析只获取当前价格和财务数据，不获取历史日线数据")

                # 优化策略：基本面分析不需要大量历史日线数据
                # 只获取当前股价信息（最近1-2天即可）和基本面财务数据
                try:
                    # 获取最新股价信息（只需要最近1-2天的数据）
                    from datetime import datetime, timedelta
                    recent_end_date = curr_date
                    recent_start_date = (datetime.strptime(curr_date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')

                    from tradingagents.dataflows.interface import get_china_stock_data_unified
                    logger.info(f"🔍 [股票代码追踪] 调用 get_china_stock_data_unified（仅获取最新价格），传入参数: ticker='{ticker}', start_date='{recent_start_date}', end_date='{recent_end_date}'")
                    current_price_data = get_china_stock_data_unified(ticker, recent_start_date, recent_end_date)

                    # 🔍 调试：打印返回数据的前500字符
                    logger.info(f"🔍 [基本面工具调试] A股价格数据返回长度: {len(current_price_data)}")
                    logger.info(f"🔍 [基本面工具调试] A股价格数据前500字符:\n{current_price_data[:500]}")

                    result_data.append(f"## A股当前价格信息\n{current_price_data}")
                except Exception as e:
                    logger.error(f"❌ [基本面工具调试] A股价格数据获取失败: {e}")
                    result_data.append(f"## A股当前价格信息\n获取失败: {e}")
                    current_price_data = ""

                try:
                    # 获取基本面财务数据（这是基本面分析的核心）
                    from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider
                    analyzer = OptimizedChinaDataProvider()
                    logger.info(f"🔍 [股票代码追踪] 调用 OptimizedChinaDataProvider._generate_fundamentals_report，传入参数: ticker='{ticker}', analysis_modules='{analysis_modules}'")

                    # 传递分析模块参数到基本面分析方法
                    fundamentals_data = analyzer._generate_fundamentals_report(ticker, current_price_data, analysis_modules)

                    # 🔍 调试：打印返回数据的前500字符
                    logger.info(f"🔍 [基本面工具调试] A股基本面数据返回长度: {len(fundamentals_data)}")
                    logger.info(f"🔍 [基本面工具调试] A股基本面数据前500字符:\n{fundamentals_data[:500]}")

                    result_data.append(f"## A股基本面财务数据\n{fundamentals_data}")
                except Exception as e:
                    logger.error(f"❌ [基本面工具调试] A股基本面数据获取失败: {e}")
                    result_data.append(f"## A股基本面财务数据\n获取失败: {e}")

            elif is_hk:
                # 港股：使用AKShare数据源，支持多重备用方案
                logger.info(f"🇭🇰 [统一基本面工具] 处理港股数据，数据深度: {data_depth}...")

                hk_data_success = False

                # 🔥 统一策略：所有级别都获取完整数据
                # 原因：提示词是统一的，如果数据不完整会导致LLM基于不存在的数据进行分析（幻觉）
                logger.info(f"🔍 [港股基本面] 统一策略：获取完整数据（忽略 data_depth 参数）")

                # 主要数据源：AKShare
                try:
                    from tradingagents.dataflows.interface import get_hk_stock_data_unified
                    hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)

                    # 🔍 调试：打印返回数据的前500字符
                    logger.info(f"🔍 [基本面工具调试] 港股数据返回长度: {len(hk_data)}")
                    logger.info(f"🔍 [基本面工具调试] 港股数据前500字符:\n{hk_data[:500]}")

                    # 检查数据质量
                    if hk_data and len(hk_data) > 100 and "❌" not in hk_data:
                        result_data.append(f"## 港股数据\n{hk_data}")
                        hk_data_success = True
                        logger.info(f"✅ [统一基本面工具] 港股主要数据源成功")
                    else:
                        logger.warning(f"⚠️ [统一基本面工具] 港股主要数据源质量不佳")

                except Exception as e:
                    logger.error(f"❌ [基本面工具调试] 港股数据获取失败: {e}")

                # 备用方案：基础港股信息
                if not hk_data_success:
                    try:
                        from tradingagents.dataflows.interface import get_hk_stock_info_unified
                        hk_info = get_hk_stock_info_unified(ticker)

                        basic_info = f"""## 港股基础信息

**股票代码**: {ticker}
**股票名称**: {hk_info.get('name', f'港股{ticker}')}
**交易货币**: 港币 (HK$)
**交易所**: 香港交易所 (HKG)
**数据源**: {hk_info.get('source', '基础信息')}

⚠️ 注意：详细的价格和财务数据暂时无法获取，建议稍后重试或使用其他数据源。

**基本面分析建议**：
- 建议查看公司最新财报
- 关注港股市场整体走势
- 考虑汇率因素对投资的影响
"""
                        result_data.append(basic_info)
                        logger.info(f"✅ [统一基本面工具] 港股备用信息成功")

                    except Exception as e2:
                        # 最终备用方案
                        fallback_info = f"""## 港股信息（备用）

**股票代码**: {ticker}
**股票类型**: 港股
**交易货币**: 港币 (HK$)
**交易所**: 香港交易所 (HKG)

❌ 数据获取遇到问题: {str(e2)}

**建议**：
- 请稍后重试
- 或使用其他数据源
- 检查股票代码格式是否正确
"""
                        result_data.append(fallback_info)
                        logger.error(f"❌ [统一基本面工具] 港股所有数据源都失败: {e2}")

            elif market_info.get('is_tw'):
                # 台股：使用TWSE数据源和Yahoo Finance
                logger.info(f"🇹🇼 [统一基本面工具] 处理台股数据，数据深度: {data_depth}...")

                tw_data_success = False

                # 🔥 统一策略：所有级别都获取完整数据
                # 原因：提示词是统一的，如果数据不完整会导致LLM基于不存在的数据进行分析（幻觉）
                logger.info(f"🔍 [台股基本面] 统一策略：获取完整数据（忽略 data_depth 参数）")

                # 主要数据源：TWSE (Taiwan Stock Exchange)
                try:
                    from app.services.data_sources.twse_adapter import TWSEAdapter
                    adapter = TWSEAdapter()
                    
                    # Remove .TW suffix if present
                    clean_code = ticker.replace('.TW', '').replace('.TWO', '')
                    
                    logger.info(f"🇹🇼 [台股基本面] 使用TWSE获取 {clean_code} 的数据...")
                    
                    # Get K-line data for price information
                    kline_data = adapter.get_kline(clean_code, period="day", limit=30)
                    
                    if kline_data and len(kline_data) > 0:
                        # Format kline data into readable report
                        latest_data = kline_data[-1]
                        price_info = f"""## 台股价格信息 (TWSE数据源)

**股票代码**: {ticker}
**最新交易日期**: {latest_data['time']}
**收盘价**: NT$ {latest_data['close']:.2f}
**开盘价**: NT$ {latest_data['open']:.2f}
**最高价**: NT$ {latest_data['high']:.2f}
**最低价**: NT$ {latest_data['low']:.2f}
**成交量**: {latest_data['volume']:,.0f}

### 近期价格走势
"""
                        # Add recent price trend
                        recent_days = min(5, len(kline_data))
                        for record in kline_data[-recent_days:]:
                            change = ((record['close'] - record['open']) / record['open'] * 100) if record['open'] else 0
                            trend = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                            price_info += f"- {record['time']}: 收盘 NT${record['close']:.2f} ({change:+.2f}%) {trend}\n"
                        
                        result_data.append(price_info)
                        tw_data_success = True
                        logger.info(f"✅ [统一基本面工具] 台股TWSE数据源成功")
                    else:
                        logger.warning(f"⚠️ [统一基本面工具] 台股TWSE数据源返回空数据")

                except Exception as e:
                    logger.error(f"❌ [基本面工具调试] 台股TWSE数据获取失败: {e}")

                # 备用数据源：Yahoo Finance (可能有更多财务数据)
                try:
                    import yfinance as yf
                    
                    logger.info(f"🇹🇼 [台股基本面] 尝试使用Yahoo Finance获取财务数据...")
                    
                    # Determine correct Yahoo Finance suffix (.TW for TWSE, .TWO for TPEx)
                    if ticker.upper().endswith('.TW') or ticker.upper().endswith('.TWO'):
                        # Already has suffix, use as-is
                        yahoo_ticker = ticker.upper()
                    else:
                        # Need to determine market: Check if it's TPEx (櫃買中心) stock
                        # TPEx stocks typically have market='OTC' or 'TWO' in twstock
                        try:
                            import twstock
                            codes = twstock.codes
                            if clean_code in codes:
                                stock_info = codes[clean_code]
                                # Check if it's OTC/TPEx market
                                if hasattr(stock_info, 'market') and stock_info.market == 'OTC':
                                    yahoo_ticker = f"{clean_code}.TWO"
                                    logger.info(f"🇹🇼 [台股基本面] 检测到櫃买中心(TPEx)股票，使用 .TWO 后缀: {yahoo_ticker}")
                                else:
                                    yahoo_ticker = f"{clean_code}.TW"
                                    logger.info(f"🇹🇼 [台股基本面] 检测到上市(TWSE)股票，使用 .TW 后缀: {yahoo_ticker}")
                            else:
                                # Fallback: try .TW first
                                yahoo_ticker = f"{clean_code}.TW"
                                logger.info(f"🇹🇼 [台股基本面] 未找到股票信息，默认使用 .TW 后缀")
                        except Exception as e:
                            # Fallback: try .TW first
                            yahoo_ticker = f"{clean_code}.TW"
                            logger.warning(f"⚠️ [台股基本面] 无法判断市场类型: {e}，默认使用 .TW 后缀")
                    
                    logger.info(f"🇹🇼 [台股基本面] Yahoo Finance ticker: {yahoo_ticker}")
                    stock = yf.Ticker(yahoo_ticker)
                    
                    # Get basic info
                    info = stock.info
                    
                    # Check if we got valid data, if not try alternative suffix
                    if not info or len(info) == 0 or info.get('regularMarketPrice') is None:
                        logger.warning(f"⚠️ [台股基本面] {yahoo_ticker} 无数据，尝试替代后缀...")
                        # Try alternative suffix
                        if yahoo_ticker.endswith('.TW'):
                            alternative_ticker = yahoo_ticker.replace('.TW', '.TWO')
                        elif yahoo_ticker.endswith('.TWO'):
                            alternative_ticker = yahoo_ticker.replace('.TWO', '.TW')
                        else:
                            alternative_ticker = None
                        
                        if alternative_ticker:
                            logger.info(f"🇹🇼 [台股基本面] 尝试替代ticker: {alternative_ticker}")
                            stock = yf.Ticker(alternative_ticker)
                            info = stock.info
                            if info and len(info) > 0 and info.get('regularMarketPrice') is not None:
                                yahoo_ticker = alternative_ticker  # Update to working ticker
                                logger.info(f"✅ [台股基本面] 替代ticker成功: {yahoo_ticker}")
                            else:
                                logger.warning(f"⚠️ [台股基本面] 替代ticker也无数据")
                    
                    if info and len(info) > 0:
                        # 🔥 优先使用twstock的中文名称（更准确），Yahoo Finance的名称作为备用
                        company_name_display = ticker  # Default fallback
                        try:
                            import twstock
                            codes = twstock.codes
                            if clean_code in codes:
                                company_name_display = codes[clean_code].name
                                logger.info(f"✅ [台股基本面] 使用twstock中文名称: {company_name_display}")
                            else:
                                # Use Yahoo Finance name if twstock doesn't have it
                                company_name_display = info.get('longName', info.get('shortName', ticker))
                                logger.warning(f"⚠️ [台股基本面] twstock无此股票，使用Yahoo Finance名称: {company_name_display}")
                        except Exception as e:
                            # Fallback to Yahoo Finance name
                            company_name_display = info.get('longName', info.get('shortName', ticker))
                            logger.warning(f"⚠️ [台股基本面] 无法获取twstock名称: {e}，使用Yahoo Finance名称")
                        
                        # Extract key financial metrics
                        yahoo_info = f"""## 台股财务信息 (Yahoo Finance)

**公司名称**: {company_name_display}
**股票代码**: {ticker}
**行业**: {info.get('industry', '未知')}
**板块**: {info.get('sector', '未知')}
**市值**: NT$ {info.get('marketCap', 0):,.0f}
**每股收益(EPS)**: NT$ {info.get('trailingEps', 'N/A')}
**市盈率(P/E)**: {info.get('trailingPE', 'N/A')}
**股息率**: {info.get('dividendYield', 0) * 100:.2f}% (如有)
**52周最高**: NT$ {info.get('fiftyTwoWeekHigh', 'N/A')}
**52周最低**: NT$ {info.get('fiftyTwoWeekLow', 'N/A')}

### 公司概况
{info.get('longBusinessSummary', '无公司简介')}
"""
                        result_data.append(yahoo_info)
                        tw_data_success = True
                        logger.info(f"✅ [统一基本面工具] 台股Yahoo Finance财务数据成功")
                    else:
                        logger.warning(f"⚠️ [统一基本面工具] Yahoo Finance无法获取 {yahoo_ticker} 的数据")

                except Exception as e:
                    logger.warning(f"⚠️ [台股基本面] Yahoo Finance获取失败: {e}")

                # 如果所有数据源都失败，提供基础信息
                if not tw_data_success:
                    try:
                        import twstock
                        codes = twstock.codes
                        
                        clean_code = ticker.replace('.TW', '').replace('.TWO', '')
                        
                        if clean_code in codes:
                            stock_info = codes[clean_code]
                            basic_info = f"""## 台股基础信息

**股票代码**: {ticker}
**股票名称**: {stock_info.name}
**交易所**: {stock_info.market if hasattr(stock_info, 'market') else '台湾证券交易所'}
**股票类型**: {stock_info.type if hasattr(stock_info, 'type') else '股票'}
**行业**: {stock_info.group if hasattr(stock_info, 'group') else '未知'}

⚠️ 注意：详细的价格和财务数据暂时无法获取，建议稍后重试。

**基本面分析建议**：
- 建议查看公司最新财报
- 关注台股大盘走势 (加权指数)
- 考虑新台币汇率因素
- 查看公司在台湾证交所的公告
"""
                            result_data.append(basic_info)
                            logger.info(f"✅ [统一基本面工具] 台股备用信息成功")
                        else:
                            raise ValueError(f"股票代码 {clean_code} 不存在")

                    except Exception as e2:
                        # 最终备用方案
                        fallback_info = f"""## 台股信息（备用）

**股票代码**: {ticker}
**股票类型**: 台股
**交易货币**: 新台币 (NT$)
**交易所**: 台湾证券交易所 (TWSE)

❌ 数据获取遇到问题: {str(e2)}

**建议**：
- 请确认股票代码是否正确（格式：2330.TW 或 2330）
- 检查该股票是否在台湾证交所上市
- 建议稍后重试或使用其他数据源
- 可访问台湾证交所官网查询: https://www.twse.com.tw
"""
                        result_data.append(fallback_info)
                        logger.error(f"❌ [统一基本面工具] 台股所有数据源都失败: {e2}")

            else:
                # 美股：使用Yahoo Finance作为主要数据源（更可靠）
                logger.info(f"🇺🇸 [统一基本面工具] 处理美股数据...")

                # 🔥 统一策略：所有级别都获取完整数据
                # 原因：提示词是统一的，如果数据不完整会导致LLM基于不存在的数据进行分析（幻觉）
                logger.info(f"🔍 [美股基本面] 统一策略：获取完整数据（忽略 data_depth 参数）")

                us_data_success = False

                # 🔥 主要数据源1：Yahoo Finance (yfinance) - 免费且可靠
                try:
                    import yfinance as yf
                    
                    logger.info(f"🇺🇸 [美股基本面] 使用Yahoo Finance (yfinance) 获取数据...")
                    
                    stock = yf.Ticker(ticker.upper())
                    info = stock.info
                    
                    logger.info(f"🔍 [美股基本面] Yahoo Finance返回数据字段数: {len(info) if info else 0}")
                    
                    # 🔥 降低数据完整性要求：即使数据不完整也尝试使用
                    # 原因：某些股票(如COHR)可能Yahoo返回的字段较少，但仍有基本信息
                    if info and len(info) > 0:  # 只要有任何数据就尝试使用
                        # Check if we have at least some key data
                        has_basic_data = any([
                            info.get('longName'),
                            info.get('shortName'),
                            info.get('currentPrice'),
                            info.get('regularMarketPrice'),
                            info.get('marketCap')
                        ])
                        
                        if has_basic_data:
                            us_data = f"""## 美股基本面数据 (Yahoo Finance)

### 公司信息
- **公司名称**: {info.get('longName', info.get('shortName', ticker))}
- **股票代码**: {ticker.upper()}
- **行业**: {info.get('industry', '未知')}
- **板块**: {info.get('sector', '未知')}
- **网站**: {info.get('website', 'N/A')}
- **员工人数**: {info.get('fullTimeEmployees', 'N/A'):,}

### 估值指标
- **市值**: ${info.get('marketCap', 0):,.0f}
- **市盈率 (P/E)**: {info.get('trailingPE', 'N/A')}
- **前瞻市盈率**: {info.get('forwardPE', 'N/A')}
- **市净率 (P/B)**: {info.get('priceToBook', 'N/A')}
- **市销率 (P/S)**: {info.get('priceToSalesTrailing12Months', 'N/A')}

### 财务指标
- **总收入**: ${info.get('totalRevenue', 0):,.0f}
- **毛利润**: ${info.get('grossProfits', 0):,.0f}
- **EBITDA**: ${info.get('ebitda', 0):,.0f}
- **每股收益 (EPS)**: ${info.get('trailingEps', 'N/A')}
- **每股账面价值**: ${info.get('bookValue', 'N/A')}

### 盈利能力
- **利润率**: {info.get('profitMargins', 0) * 100:.2f}%
- **营业利润率**: {info.get('operatingMargins', 0) * 100:.2f}%
- **净资产收益率 (ROE)**: {info.get('returnOnEquity', 0) * 100:.2f}%
- **总资产收益率 (ROA)**: {info.get('returnOnAssets', 0) * 100:.2f}%

### 股价信息
- **当前价格**: ${info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))}
- **52周最高**: ${info.get('fiftyTwoWeekHigh', 'N/A')}
- **52周最低**: ${info.get('fiftyTwoWeekLow', 'N/A')}
- **50日均线**: ${info.get('fiftyDayAverage', 'N/A')}
- **200日均线**: ${info.get('twoHundredDayAverage', 'N/A')}

### 股息信息
- **股息率**: {info.get('dividendYield', 0) * 100:.2f}%
- **每股股息**: ${info.get('dividendRate', 'N/A')}
- **派息率**: {info.get('payoutRatio', 0) * 100:.2f}%

### 分析师评级
- **目标价**: ${info.get('targetMeanPrice', 'N/A')}
- **推荐评级**: {info.get('recommendationKey', 'N/A').upper() if info.get('recommendationKey') else 'N/A'}
- **分析师数量**: {info.get('numberOfAnalystOpinions', 'N/A')}

### 公司概况
{info.get('longBusinessSummary', '无公司简介')}

**数据来源**: Yahoo Finance (yfinance)
**数据获取时间**: {curr_date}
"""
                            result_data.append(us_data)
                            us_data_success = True
                            logger.info(f"✅ [统一基本面工具] 美股Yahoo Finance数据获取成功，数据长度: {len(us_data)}")
                        else:
                            logger.warning(f"⚠️ [美股基本面] Yahoo Finance数据无关键字段，info: {list(info.keys())[:20] if info else 'None'}")
                    else:
                        logger.warning(f"⚠️ [美股基本面] Yahoo Finance返回空数据或数据不足")
                        if info:
                            logger.info(f"🔍 [美股基本面] Yahoo返回的字段: {list(info.keys())}")
                
                except Exception as e:
                    logger.error(f"❌ [美股基本面] Yahoo Finance获取异常: {e}", exc_info=True)

                # 🔥 主要数据源2：Alpha Vantage (如果配置了API key)
                if not us_data_success:
                    import os
                    alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
                    
                    if alpha_vantage_key:
                        logger.info(f"🇺🇸 [美股基本面] Yahoo Finance失败，尝试Alpha Vantage (已配置API key)...")
                        try:
                            from tradingagents.dataflows.providers.us.alpha_vantage_fundamentals import get_fundamentals as get_av_fundamentals
                            
                            av_data = get_av_fundamentals(ticker, curr_date)
                            
                            if av_data and "Error" not in av_data and "error" not in av_data.lower() and len(av_data) > 100:
                                result_data.append(f"## 美股基本面数据 (Alpha Vantage)\n{av_data}")
                                us_data_success = True
                                logger.info(f"✅ [统一基本面工具] 美股Alpha Vantage数据获取成功")
                            else:
                                logger.warning(f"⚠️ [美股基本面] Alpha Vantage数据质量不佳或返回错误")
                        except Exception as e:
                            logger.error(f"❌ [美股基本面] Alpha Vantage获取失败: {e}", exc_info=True)
                    else:
                        logger.info(f"ℹ️ [美股基本面] 未配置 ALPHA_VANTAGE_API_KEY，跳过Alpha Vantage数据源")

                # 备用数据源：get_fundamentals_openai (Finnhub/其他)
                if not us_data_success:
                    logger.info(f"🇺🇸 [美股基本面] Yahoo Finance失败，尝试备用数据源(Finnhub/Alpha Vantage)...")
                    try:
                        from tradingagents.dataflows.interface import get_fundamentals_openai
                        us_data_backup = get_fundamentals_openai(ticker, curr_date)
                        
                        # Check if backup also failed
                        if us_data_backup and "❌" not in us_data_backup and len(us_data_backup) > 100:
                            result_data.append(f"## 美股基本面数据 (备用数据源)\n{us_data_backup}")
                            logger.info(f"✅ [统一基本面工具] 美股备用数据源获取成功")
                        else:
                            # Both sources failed - provide helpful error message
                            error_msg = f"""## 美股基本面数据

❌ 无法获取 {ticker.upper()} 的基本面数据

**尝试过的数据源**:
1. Yahoo Finance (yfinance) - 失败或数据不足
2. Alpha Vantage - {'已配置但失败' if os.getenv('ALPHA_VANTAGE_API_KEY') else '未配置API密钥'}
3. Finnhub - {'已配置但失败' if os.getenv('FINNHUB_API_KEY') else '未配置API密钥'}

**可能的原因**:
- 股票代码可能不正确或已退市
- 网络连接问题
- API配额限制（Alpha Vantage免费版：5次/分钟，500次/天）

**建议**:
- 检查股票代码是否正确: {ticker.upper()}
- 配置API密钥以启用更多数据源:
  export ALPHA_VANTAGE_API_KEY="your_key"  # 获取: https://www.alphavantage.co/support/#api-key
  export FINNHUB_API_KEY="your_key"        # 获取: https://finnhub.io/register
- 检查网络连接
- 稍后重试（可能达到API限制）

**临时解决方案**: 您可以通过市场技术分析师获取该股票的价格和技术指标数据。
"""
                            result_data.append(error_msg)
                            logger.error(f"❌ [统一基本面工具] 美股所有数据源都失败: {ticker}")
                    except Exception as e:
                        error_msg = f"""## 美股基本面数据

❌ 数据获取失败: {str(e)}

**建议**: 
- 配置 ALPHA_VANTAGE_API_KEY 环境变量
- 检查API配置和网络连接
- 稍后重试
"""
                        result_data.append(error_msg)
                        logger.error(f"❌ [统一基本面工具] 美股备用数据源异常: {e}", exc_info=True)

            # 组合所有数据
            combined_result = f"""# {ticker} 基本面分析数据

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析日期**: {curr_date}
**数据深度级别**: {data_depth}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""

            # 添加详细的数据获取日志
            logger.info(f"📊 [统一基本面工具] ===== 数据获取完成摘要 =====")
            logger.info(f"📊 [统一基本面工具] 股票代码: {ticker}")
            logger.info(f"📊 [统一基本面工具] 股票类型: {market_info['market_name']}")
            logger.info(f"📊 [统一基本面工具] 数据深度级别: {data_depth}")
            logger.info(f"📊 [统一基本面工具] 获取的数据模块数量: {len(result_data)}")
            logger.info(f"📊 [统一基本面工具] 总数据长度: {len(combined_result)} 字符")
            
            # 记录每个数据模块的详细信息
            for i, data_section in enumerate(result_data, 1):
                section_lines = data_section.split('\n')
                section_title = section_lines[0] if section_lines else "未知模块"
                section_length = len(data_section)
                logger.info(f"📊 [统一基本面工具] 数据模块 {i}: {section_title} ({section_length} 字符)")
                
                # 如果数据包含错误信息，特别标记
                if "获取失败" in data_section or "❌" in data_section:
                    logger.warning(f"⚠️ [统一基本面工具] 数据模块 {i} 包含错误信息")
                else:
                    logger.info(f"✅ [统一基本面工具] 数据模块 {i} 获取成功")
            
            # 根据数据深度级别记录具体的获取策略
            if data_depth in ["basic", "standard"]:
                logger.info(f"📊 [统一基本面工具] 基础/标准级别策略: 仅获取核心价格数据和基础信息")
            elif data_depth in ["full", "detailed", "comprehensive"]:
                logger.info(f"📊 [统一基本面工具] 完整/详细/全面级别策略: 获取价格数据 + 基本面数据")
            else:
                logger.info(f"📊 [统一基本面工具] 默认策略: 获取完整数据")
            
            logger.info(f"📊 [统一基本面工具] ===== 数据获取摘要结束 =====")
            
            return combined_result

        except Exception as e:
            error_msg = f"统一基本面分析工具执行失败: {str(e)}"
            logger.error(f"❌ [统一基本面工具] {error_msg}")
            return error_msg

    @staticmethod
    @tool
    @log_tool_call(tool_name="get_stock_market_data_unified", log_args=True)
    def get_stock_market_data_unified(
        ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
        start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD。注意：系统会自动扩展到配置的回溯天数（通常为365天），你只需要传递分析日期即可"],
        end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD。通常与start_date相同，传递当前分析日期即可"]
    ) -> str:
        """
        统一的股票市场数据工具
        自动识别股票类型（A股、港股、美股）并调用相应的数据源获取价格和技术指标数据

        ⚠️ 重要：系统会自动扩展日期范围到配置的回溯天数（通常为365天），以确保技术指标计算有足够的历史数据。
        你只需要传递当前分析日期作为 start_date 和 end_date 即可，无需手动计算历史日期范围。

        Args:
            ticker: 股票代码（如：000001、0700.HK、AAPL）
            start_date: 开始日期（格式：YYYY-MM-DD）。传递当前分析日期即可，系统会自动扩展
            end_date: 结束日期（格式：YYYY-MM-DD）。传递当前分析日期即可

        Returns:
            str: 市场数据和技术分析报告

        示例：
            如果分析日期是 2025-11-09，传递：
            - ticker: "00700.HK"
            - start_date: "2025-11-09"
            - end_date: "2025-11-09"
            系统会自动获取 2024-11-09 到 2025-11-09 的365天历史数据
        """
        logger.info(f"📈 [统一市场工具] 分析股票: {ticker}")
        logger.info(f"📈 [统一市场工具] 请求日期范围: {start_date} 至 {end_date}")

        try:
            from tradingagents.utils.stock_utils import StockUtils
            from datetime import datetime, timedelta

            # 🔥 智能日期处理：如果当日数据为空（未收盘），自动回退到前一交易日
            original_end_date = end_date
            should_fallback_to_previous_day = False
            
            # 检查当前时间是否已收盘
            try:
                current_time = datetime.now()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                
                # 如果分析日期是今天或未来，可能还没有收盘数据
                if end_date_obj.date() >= current_time.date():
                    logger.warning(f"⚠️ [统一市场工具] 分析日期 {end_date} 是今天或未来，可能无收盘数据")
                    should_fallback_to_previous_day = True
            except Exception as e:
                logger.warning(f"⚠️ [统一市场工具] 日期检查失败: {e}")

            # 自动识别股票类型
            market_info = StockUtils.get_market_info(ticker)
            is_china = market_info['is_china']
            is_hk = market_info['is_hk']
            is_us = market_info['is_us']

            logger.info(f"📈 [统一市场工具] 股票类型: {market_info['market_name']}")
            logger.info(f"📈 [统一市场工具] 货币: {market_info['currency_name']} ({market_info['currency_symbol']}")

            result_data = []

            if is_china:
                # 中国A股：使用中国股票数据源
                logger.info(f"🇨🇳 [统一市场工具] 处理A股市场数据...")

                try:
                    from tradingagents.dataflows.interface import get_china_stock_data_unified
                    stock_data = get_china_stock_data_unified(ticker, start_date, end_date)

                    # 🔍 调试：打印返回数据的前500字符
                    logger.info(f"🔍 [市场工具调试] A股数据返回长度: {len(stock_data)}")
                    logger.info(f"🔍 [市场工具调试] A股数据前500字符:\n{stock_data[:500]}")

                    result_data.append(f"## A股市场数据\n{stock_data}")
                except Exception as e:
                    logger.error(f"❌ [市场工具调试] A股数据获取失败: {e}")
                    result_data.append(f"## A股市场数据\n获取失败: {e}")

            elif is_hk:
                # 港股：使用AKShare数据源
                logger.info(f"🇭🇰 [统一市场工具] 处理港股市场数据...")

                try:
                    from tradingagents.dataflows.interface import get_hk_stock_data_unified
                    hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)

                    # 🔍 调试：打印返回数据的前500字符
                    logger.info(f"🔍 [市场工具调试] 港股数据返回长度: {len(hk_data)}")
                    logger.info(f"🔍 [市场工具调试] 港股数据前500字符:\n{hk_data[:500]}")

                    result_data.append(f"## 港股市场数据\n{hk_data}")
                except Exception as e:
                    logger.error(f"❌ [市场工具调试] 港股数据获取失败: {e}")
                    result_data.append(f"## 港股市场数据\n获取失败: {e}")

            elif market_info.get('is_tw'):
                # 台股：优先使用Yahoo Finance（更可靠的数据），TWSE作为备用
                logger.info(f"🇹🇼 [统一市场工具] 处理台股市场数据...")

                tw_data_success = False

                # 🔥 主要数据源：Yahoo Finance (更可靠，有完整的OHLCV数据)
                try:
                    import yfinance as yf
                    import pandas as pd
                    
                    logger.info(f"🇹🇼 [统一市场工具] 优先使用Yahoo Finance获取台股数据...")
                    
                    # Determine correct suffix (.TW or .TWO)
                    clean_code = ticker.replace('.TW', '').replace('.TWO', '')
                    
                    # Try to determine correct suffix
                    yahoo_ticker = ticker if (ticker.upper().endswith('.TW') or ticker.upper().endswith('.TWO')) else f"{clean_code}.TW"
                    
                    # Try to detect TPEx stocks
                    try:
                        import twstock
                        codes = twstock.codes
                        if clean_code in codes:
                            stock_info = codes[clean_code]
                            if hasattr(stock_info, 'market') and stock_info.market == 'OTC':
                                yahoo_ticker = f"{clean_code}.TWO"
                    except:
                        pass
                    
                    logger.info(f"🇹🇼 [台股市场] Yahoo Finance ticker: {yahoo_ticker}")
                    
                    # Fetch data from Yahoo Finance
                    stock = yf.Ticker(yahoo_ticker)
                    
                    # Calculate period to fetch
                    from datetime import datetime, timedelta
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    
                    # 🔥 Extend by 90 days to ensure enough historical data for technical analysis
                    # This provides ~60 trading days which is needed for MA60 and other indicators
                    extended_start = (end_dt - timedelta(days=90)).strftime('%Y-%m-%d')
                    logger.info(f"📊 [台股市场] 扩展数据范围: {extended_start} 至 {end_date} (约90天)")
                    
                    # Get historical data
                    hist = stock.history(start=extended_start, end=(end_dt + timedelta(days=1)).strftime('%Y-%m-%d'))
                    
                    # Try alternative suffix if no data
                    if hist.empty:
                        logger.warning(f"⚠️ [台股市场] {yahoo_ticker} 无数据，尝试替代后缀...")
                        alternative_ticker = yahoo_ticker.replace('.TW', '.TWO') if '.TW' in yahoo_ticker else yahoo_ticker.replace('.TWO', '.TW')
                        logger.info(f"🇹🇼 [台股市场] 尝试: {alternative_ticker}")
                        stock = yf.Ticker(alternative_ticker)
                        hist = stock.history(start=extended_start, end=(end_dt + timedelta(days=1)).strftime('%Y-%m-%d'))
                        if not hist.empty:
                            yahoo_ticker = alternative_ticker
                            logger.info(f"✅ [台股市场] 替代ticker成功: {yahoo_ticker}")
                    
                    if not hist.empty:
                        # Format Yahoo Finance data with COMPLETE historical K-line data
                        tw_report = f"""### 台股市场数据摘要 (Yahoo Finance)

**数据期间**: {extended_start} 至 {end_date}
**数据点数**: {len(hist)} 个交易日
**数据源**: Yahoo Finance ({yahoo_ticker})

#### 最新交易数据
- **日期**: {hist.index[-1].strftime('%Y-%m-%d')}
- **收盘价**: NT$ {hist['Close'].iloc[-1]:.2f}
- **开盘价**: NT$ {hist['Open'].iloc[-1]:.2f}
- **最高价**: NT$ {hist['High'].iloc[-1]:.2f}
- **最低价**: NT$ {hist['Low'].iloc[-1]:.2f}
- **成交量**: {hist['Volume'].iloc[-1]:,.0f} 张
- **涨跌幅**: {((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0:.2f}%

#### 历史K线数据 (最近30日)
| 日期 | 开盘 | 最高 | 最低 | 收盘 | 成交量 | 涨跌幅 |
|------|------|------|------|------|--------|--------|
"""
                        # Add last 30 days of K-line data
                        kline_days = min(30, len(hist))
                        for i in range(kline_days):
                            idx = -(kline_days - i)
                            date = hist.index[idx].strftime('%Y-%m-%d')
                            open_price = hist['Open'].iloc[idx]
                            high = hist['High'].iloc[idx]
                            low = hist['Low'].iloc[idx]
                            close = hist['Close'].iloc[idx]
                            volume = hist['Volume'].iloc[idx]
                            if idx > -len(hist):
                                change = ((hist['Close'].iloc[idx] - hist['Close'].iloc[idx-1]) / hist['Close'].iloc[idx-1] * 100)
                                tw_report += f"| {date} | {open_price:.2f} | {high:.2f} | {low:.2f} | {close:.2f} | {volume:,.0f} | {change:+.2f}% |\n"
                            else:
                                tw_report += f"| {date} | {open_price:.2f} | {high:.2f} | {low:.2f} | {close:.2f} | {volume:,.0f} | - |\n"

                        tw_report += f"""
#### 价格统计
- **期间最高**: NT$ {hist['High'].max():.2f}
- **期间最低**: NT$ {hist['Low'].min():.2f}
- **平均收盘价**: NT$ {hist['Close'].mean():.2f}
- **价格波动率**: {hist['Close'].std():.2f}

#### 成交量统计
- **平均成交量**: {hist['Volume'].mean():,.0f} 张
- **最大成交量**: {hist['Volume'].max():,.0f} 张
- **最小成交量**: {hist['Volume'].min():,.0f} 张

#### 技术指标
"""
                        # Calculate technical indicators
                        if len(hist) >= 5:
                            ma5 = hist['Close'].tail(5).mean()
                            tw_report += f"- **5日均线 (MA5)**: NT$ {ma5:.2f}\n"
                            current_vs_ma5 = ((hist['Close'].iloc[-1] - ma5) / ma5 * 100)
                            tw_report += f"  - 当前价格 vs MA5: {current_vs_ma5:+.2f}% {'(上穿)' if current_vs_ma5 > 0 else '(下穿)'}\n"
                        
                        if len(hist) >= 20:
                            ma20 = hist['Close'].tail(20).mean()
                            tw_report += f"- **20日均线 (MA20)**: NT$ {ma20:.2f}\n"
                            current_vs_ma20 = ((hist['Close'].iloc[-1] - ma20) / ma20 * 100)
                            tw_report += f"  - 当前价格 vs MA20: {current_vs_ma20:+.2f}% {'(上穿)' if current_vs_ma20 > 0 else '(下穿)'}\n"
                        
                        if len(hist) >= 60:
                            ma60 = hist['Close'].tail(60).mean()
                            tw_report += f"- **60日均线 (MA60)**: NT$ {ma60:.2f}\n"
                            current_vs_ma60 = ((hist['Close'].iloc[-1] - ma60) / ma60 * 100)
                            tw_report += f"  - 当前价格 vs MA60: {current_vs_ma60:+.2f}% {'(上穿)' if current_vs_ma60 > 0 else '(下穿)'}\n"
                        
                        # Add volatility indicator
                        if len(hist) >= 20:
                            volatility_20d = hist['Close'].tail(20).std() / hist['Close'].tail(20).mean() * 100
                            tw_report += f"- **20日波动率**: {volatility_20d:.2f}%\n"
                        
                        # Add volume trend
                        if len(hist) >= 5:
                            avg_volume_5d = hist['Volume'].tail(5).mean()
                            avg_volume_20d = hist['Volume'].tail(20).mean() if len(hist) >= 20 else avg_volume_5d
                            volume_trend = ((avg_volume_5d - avg_volume_20d) / avg_volume_20d * 100) if avg_volume_20d > 0 else 0
                            tw_report += f"- **成交量趋势**: 5日均量 vs 20日均量 {volume_trend:+.2f}%\n"
                        
                        # Add trend analysis
                        tw_report += "\n#### 价格趋势分析\n"
                        if len(hist) >= 20:
                            recent_close = hist['Close'].iloc[-1]
                            if recent_close > ma5 and recent_close > ma20:
                                tw_report += "- 短期趋势: **上涨** (价格位于MA5和MA20上方)\n"
                            elif recent_close < ma5 and recent_close < ma20:
                                tw_report += "- 短期趋势: **下跌** (价格位于MA5和MA20下方)\n"
                            else:
                                tw_report += "- 短期趋势: **震荡** (价格在均线之间)\n"
                        
                        result_data.append(f"## 台股市场数据\n{tw_report}")
                        tw_data_success = True
                        logger.info(f"✅ [统一市场工具] 台股Yahoo Finance数据获取成功")
                    else:
                        logger.warning(f"⚠️ [统一市场工具] Yahoo Finance {yahoo_ticker} 返回空数据")

                except Exception as e:
                    logger.error(f"❌ [市场工具调试] 台股Yahoo Finance数据获取失败: {e}")

                # 备用数据源：TWSE Adapter (如果Yahoo Finance失败)
                if not tw_data_success:
                    logger.info(f"🇹🇼 [统一市场工具] Yahoo Finance失败，尝试TWSE适配器...")
                    try:
                        from tradingagents.dataflows.data_source_manager import get_data_source_manager
                        manager = get_data_source_manager()
                        
                        # Use the manager's method to get Taiwan stock data
                        tw_data_df = manager.get_stock_dataframe(ticker, start_date, end_date)
                        
                        if tw_data_df is not None and not tw_data_df.empty:
                            # Format dataframe into readable report
                            tw_report = f"""### 台股市场数据摘要 (TWSE数据源)

**数据期间**: {start_date} 至 {end_date}
**数据点数**: {len(tw_data_df)} 个交易日

#### 最新交易数据
- **日期**: {tw_data_df.iloc[-1]['date'] if 'date' in tw_data_df.columns else tw_data_df.index[-1]}
- **收盘价**: NT$ {tw_data_df.iloc[-1]['close']:.2f}
- **涨跌幅**: {tw_data_df.iloc[-1].get('pct_change', 0):.2f}%
- **成交量**: {tw_data_df.iloc[-1].get('volume', 0):,.0f}

#### 价格统计
- **期间最高**: NT$ {tw_data_df['high'].max():.2f}
- **期间最低**: NT$ {tw_data_df['low'].min():.2f}
- **平均收盘价**: NT$ {tw_data_df['close'].mean():.2f}
- **价格波动率**: {tw_data_df['close'].std():.2f}

#### 成交量统计
- **平均成交量**: {tw_data_df['volume'].mean():,.0f}
- **最大成交量**: {tw_data_df['volume'].max():,.0f}
- **最小成交量**: {tw_data_df['volume'].min():,.0f}

#### 技术指标
"""
                            # Calculate simple technical indicators
                            if len(tw_data_df) >= 5:
                                ma5 = tw_data_df['close'].tail(5).mean()
                                tw_report += f"- **5日均线**: NT$ {ma5:.2f}\n"
                            
                            if len(tw_data_df) >= 20:
                                ma20 = tw_data_df['close'].tail(20).mean()
                                tw_report += f"- **20日均线**: NT$ {ma20:.2f}\n"
                            
                            if len(tw_data_df) >= 60:
                                ma60 = tw_data_df['close'].tail(60).mean()
                                tw_report += f"- **60日均线**: NT$ {ma60:.2f}\n"
                            
                            result_data.append(f"## 台股市场数据\n{tw_report}")
                            tw_data_success = True
                            logger.info(f"✅ [市场工具调试] 台股TWSE数据获取成功")
                        else:
                            result_data.append(f"## 台股市场数据\n❌ TWSE适配器未获取到有效数据")
                            logger.warning(f"⚠️ [市场工具调试] 台股TWSE数据为空")
                            
                    except Exception as e:
                        logger.error(f"❌ [市场工具调试] 台股TWSE数据获取失败: {e}")
                        result_data.append(f"## 台股市场数据\n获取失败: {e}")
                
                # 最终备用：如果所有数据源都失败，提供说明
                if not tw_data_success:
                    result_data.append(f"""## 台股市场数据

❌ 无法从任何数据源获取 {ticker} 的市场数据

**尝试过的数据源**:
1. Yahoo Finance ({yahoo_ticker}) - 失败
2. TWSE Adapter (twstock) - 失败

**建议**:
- 检查股票代码是否正确
- 确认股票是否仍在交易
- 稍后重试或联系技术支持
""")

            else:
                # 美股：优先使用FINNHUB API数据源
                logger.info(f"🇺🇸 [统一市场工具] 处理美股市场数据...")

                try:
                    from tradingagents.dataflows.providers.us.optimized import get_us_stock_data_cached
                    us_data = get_us_stock_data_cached(ticker, start_date, end_date)
                    result_data.append(f"## 美股市场数据\n{us_data}")
                except Exception as e:
                    result_data.append(f"## 美股市场数据\n获取失败: {e}")

            # 🔥 智能回退：检查数据是否为空，如果是则尝试前一交易日
            if should_fallback_to_previous_day and (not result_data or all("获取失败" in str(d) or "❌" in str(d) or "未获取到" in str(d) for d in result_data)):
                logger.warning(f"⚠️ [统一市场工具] {end_date} 无有效数据，尝试回退到前一交易日...")
                
                # 🔥 智能回退策略：回退至少3天，跳过周末
                # - 如果今天是周一(0)，回退到上周五(-3天)
                # - 如果今天是周日(6)，回退到上周五(-2天)
                # - 如果今天是周六(5)，回退到上周五(-1天)
                # - 其他工作日，回退到前一天(-1天)
                # 为了保险起见，统一回退5天，让数据源自动处理节假日
                
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
                day_of_week = end_date_obj.weekday()  # 0=Monday, 6=Sunday
                
                # 根据星期几决定回退天数
                if day_of_week == 0:  # Monday
                    days_back = 3  # 回退到周五
                    logger.info(f"📅 [统一市场工具] 检测到周一，回退3天到周五")
                elif day_of_week == 6:  # Sunday
                    days_back = 2  # 回退到周五
                    logger.info(f"📅 [统一市场工具] 检测到周日，回退2天到周五")
                elif day_of_week == 5:  # Saturday
                    days_back = 1  # 回退到周五
                    logger.info(f"📅 [统一市场工具] 检测到周六，回退1天到周五")
                else:  # Tuesday-Friday
                    days_back = 1  # 回退到前一个工作日
                    logger.info(f"📅 [统一市场工具] 工作日，回退1天")
                
                previous_date = (end_date_obj - timedelta(days=days_back)).strftime('%Y-%m-%d')
                logger.info(f"🔄 [统一市场工具] 回退日期: {end_date} ({['周一','周二','周三','周四','周五','周六','周日'][day_of_week]}) → {previous_date}")
                
                # 🔥 为了确保获取到数据，start_date也回退，保证至少有3-5天的历史数据
                # 这样即使previous_date也是节假日，数据源也能返回最近的有效交易日数据
                safe_start_date = (end_date_obj - timedelta(days=7)).strftime('%Y-%m-%d')  # 回退7天作为起始日期
                logger.info(f"📅 [统一市场工具] 调整起始日期: {start_date} → {safe_start_date}，确保获取足够历史数据")
                
                # 重新获取数据
                result_data = []  # 清空之前的结果
                end_date = previous_date  # 更新end_date
                start_date = safe_start_date  # 更新start_date，确保有足够历史数据
                
                if is_china:
                    try:
                        from tradingagents.dataflows.interface import get_china_stock_data_unified
                        stock_data = get_china_stock_data_unified(ticker, start_date, end_date)
                        result_data.append(f"## A股市场数据\n{stock_data}")
                        logger.info(f"✅ [统一市场工具] 回退成功，获取到前一日A股数据")
                    except Exception as e:
                        result_data.append(f"## A股市场数据\n回退后仍失败: {e}")
                
                elif is_hk:
                    try:
                        from tradingagents.dataflows.interface import get_hk_stock_data_unified
                        hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)
                        result_data.append(f"## 港股市场数据\n{hk_data}")
                        logger.info(f"✅ [统一市场工具] 回退成功，获取到前一日港股数据")
                    except Exception as e:
                        result_data.append(f"## 港股市场数据\n回退后仍失败: {e}")
                
                elif market_info.get('is_tw'):
                    try:
                        import yfinance as yf
                        
                        # Determine correct suffix
                        clean_code = ticker.replace('.TW', '').replace('.TWO', '')
                        yahoo_ticker = ticker if (ticker.upper().endswith('.TW') or ticker.upper().endswith('.TWO')) else f"{clean_code}.TW"
                        
                        # Try to detect TPEx
                        try:
                            import twstock
                            codes = twstock.codes
                            if clean_code in codes and hasattr(codes[clean_code], 'market') and codes[clean_code].market == 'OTC':
                                yahoo_ticker = f"{clean_code}.TWO"
                        except:
                            pass
                        
                        stock = yf.Ticker(yahoo_ticker)
                        
                        # Extend date range for more data
                        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                        extended_start = (start_dt - timedelta(days=7)).strftime('%Y-%m-%d')
                        
                        hist = stock.history(start=extended_start, end=(end_dt + timedelta(days=1)).strftime('%Y-%m-%d'))
                        
                        # Try alternative suffix if empty
                        if hist.empty:
                            alternative_ticker = yahoo_ticker.replace('.TW', '.TWO') if '.TW' in yahoo_ticker else yahoo_ticker.replace('.TWO', '.TW')
                            stock = yf.Ticker(alternative_ticker)
                            hist = stock.history(start=extended_start, end=(end_dt + timedelta(days=1)).strftime('%Y-%m-%d'))
                            if not hist.empty:
                                yahoo_ticker = alternative_ticker
                        
                        if not hist.empty:
                            tw_report = f"""### 台股市场数据摘要 (Yahoo Finance 回退)

**数据期间**: {extended_start} 至 {end_date}
**数据点数**: {len(hist)} 个交易日

#### 最新交易数据
- **日期**: {hist.index[-1].strftime('%Y-%m-%d')}
- **收盘价**: NT$ {hist['Close'].iloc[-1]:.2f}
- **成交量**: {hist['Volume'].iloc[-1]:,.0f} 张
- **涨跌幅**: {((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0:.2f}%
"""
                            result_data.append(f"## 台股市场数据\n{tw_report}")
                            logger.info(f"✅ [统一市场工具] 回退成功，获取到前一日台股数据 (Yahoo Finance)")
                        else:
                            result_data.append(f"## 台股市场数据\n回退后仍无数据 (Yahoo Finance)")
                    except Exception as e:
                        result_data.append(f"## 台股市场数据\n回退后仍失败: {e}")
                
                else:  # US stocks
                    try:
                        from tradingagents.dataflows.providers.us.optimized import get_us_stock_data_cached
                        us_data = get_us_stock_data_cached(ticker, start_date, end_date)
                        result_data.append(f"## 美股市场数据\n{us_data}")
                        logger.info(f"✅ [统一市场工具] 回退成功，获取到前一日美股数据")
                    except Exception as e:
                        result_data.append(f"## 美股市场数据\n回退后仍失败: {e}")

            # 组合所有数据
            combined_result = f"""# {ticker} 市场数据分析

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析期间**: {start_date} 至 {end_date}
{f"**说明**: 原始请求日期 {original_end_date} 无交易数据（可能是今天未收盘或非交易日），已自动回退到前一交易日 {end_date}（跳过周末和节假日）" if end_date != original_end_date else ""}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""

            logger.info(f"📈 [统一市场工具] 数据获取完成，总长度: {len(combined_result)}")
            return combined_result

        except Exception as e:
            error_msg = f"统一市场数据工具执行失败: {str(e)}"
            logger.error(f"❌ [统一市场工具] {error_msg}")
            return error_msg

    @staticmethod
    @tool
    @log_tool_call(tool_name="get_stock_news_unified", log_args=True)
    def get_stock_news_unified(
        ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
        curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"]
    ) -> str:
        """
        统一的股票新闻工具
        自动识别股票类型（A股、港股、美股）并调用相应的新闻数据源

        Args:
            ticker: 股票代码（如：000001、0700.HK、AAPL）
            curr_date: 当前日期（格式：YYYY-MM-DD）

        Returns:
            str: 新闻分析报告
        """
        logger.info(f"📰 [统一新闻工具] 分析股票: {ticker}")

        try:
            from tradingagents.utils.stock_utils import StockUtils
            from datetime import datetime, timedelta

            # 自动识别股票类型
            market_info = StockUtils.get_market_info(ticker)
            is_china = market_info['is_china']
            is_hk = market_info['is_hk']
            is_us = market_info['is_us']

            logger.info(f"📰 [统一新闻工具] 股票类型: {market_info['market_name']}")

            # 计算新闻查询的日期范围
            end_date = datetime.strptime(curr_date, '%Y-%m-%d')
            start_date = end_date - timedelta(days=7)
            start_date_str = start_date.strftime('%Y-%m-%d')

            result_data = []

            if is_china or is_hk:
                # 中国A股和港股：使用AKShare东方财富新闻和Google新闻（中文搜索）
                logger.info(f"🇨🇳🇭🇰 [统一新闻工具] 处理中文新闻...")

                # 1. 尝试获取AKShare东方财富新闻
                try:
                    # 处理股票代码
                    clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                                   .replace('.HK', '').replace('.XSHE', '').replace('.XSHG', '')
                    
                    logger.info(f"🇨🇳🇭🇰 [统一新闻工具] 尝试获取东方财富新闻: {clean_ticker}")

                    # 通过 AKShare Provider 获取新闻
                    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

                    provider = AKShareProvider()

                    # 获取东方财富新闻
                    news_df = provider.get_stock_news_sync(symbol=clean_ticker)

                    if news_df is not None and not news_df.empty:
                        # 格式化东方财富新闻
                        em_news_items = []
                        for _, row in news_df.iterrows():
                            # AKShare 返回的字段名
                            news_title = row.get('新闻标题', '') or row.get('标题', '')
                            news_time = row.get('发布时间', '') or row.get('时间', '')
                            news_url = row.get('新闻链接', '') or row.get('链接', '')

                            news_item = f"- **{news_title}** [{news_time}]({news_url})"
                            em_news_items.append(news_item)
                        
                        # 添加到结果中
                        if em_news_items:
                            em_news_text = "\n".join(em_news_items)
                            result_data.append(f"## 东方财富新闻\n{em_news_text}")
                            logger.info(f"🇨🇳🇭🇰 [统一新闻工具] 成功获取{len(em_news_items)}条东方财富新闻")
                except Exception as em_e:
                    logger.error(f"❌ [统一新闻工具] 东方财富新闻获取失败: {em_e}")
                    result_data.append(f"## 东方财富新闻\n获取失败: {em_e}")

                # 2. 获取Google新闻作为补充
                try:
                    # 获取公司中文名称用于搜索
                    if is_china:
                        # A股使用股票代码搜索，添加更多中文关键词
                        clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                                       .replace('.XSHE', '').replace('.XSHG', '')
                        search_query = f"{clean_ticker} 股票 公司 财报 新闻"
                        logger.info(f"🇨🇳 [统一新闻工具] A股Google新闻搜索关键词: {search_query}")
                    else:
                        # 港股使用代码搜索
                        search_query = f"{ticker} 港股"
                        logger.info(f"🇭🇰 [统一新闻工具] 港股Google新闻搜索关键词: {search_query}")

                    from tradingagents.dataflows.interface import get_google_news
                    news_data = get_google_news(search_query, curr_date)
                    result_data.append(f"## Google新闻\n{news_data}")
                    logger.info(f"🇨🇳🇭🇰 [统一新闻工具] 成功获取Google新闻")
                except Exception as google_e:
                    logger.error(f"❌ [统一新闻工具] Google新闻获取失败: {google_e}")
                    result_data.append(f"## Google新闻\n获取失败: {google_e}")

            else:
                # 美股：使用Finnhub新闻
                logger.info(f"🇺🇸 [统一新闻工具] 处理美股新闻...")

                try:
                    from tradingagents.dataflows.interface import get_finnhub_news
                    news_data = get_finnhub_news(ticker, start_date_str, curr_date)
                    result_data.append(f"## 美股新闻\n{news_data}")
                except Exception as e:
                    result_data.append(f"## 美股新闻\n获取失败: {e}")

            # 组合所有数据
            combined_result = f"""# {ticker} 新闻分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date}
**新闻时间范围**: {start_date_str} 至 {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的新闻源*
"""

            logger.info(f"📰 [统一新闻工具] 数据获取完成，总长度: {len(combined_result)}")
            return combined_result

        except Exception as e:
            error_msg = f"统一新闻工具执行失败: {str(e)}"
            logger.error(f"❌ [统一新闻工具] {error_msg}")
            return error_msg

    @staticmethod
    @tool
    @log_tool_call(tool_name="get_stock_sentiment_unified", log_args=True)
    def get_stock_sentiment_unified(
        ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
        curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"]
    ) -> str:
        """
        统一的股票情绪分析工具
        自动识别股票类型（A股、港股、美股）并调用相应的情绪数据源

        Args:
            ticker: 股票代码（如：000001、0700.HK、AAPL）
            curr_date: 当前日期（格式：YYYY-MM-DD）

        Returns:
            str: 情绪分析报告
        """
        logger.info(f"😊 [统一情绪工具] 分析股票: {ticker}")

        try:
            from tradingagents.utils.stock_utils import StockUtils

            # 自动识别股票类型
            market_info = StockUtils.get_market_info(ticker)
            is_china = market_info['is_china']
            is_hk = market_info['is_hk']
            is_us = market_info['is_us']

            logger.info(f"😊 [统一情绪工具] 股票类型: {market_info['market_name']}")

            result_data = []

            if is_china or is_hk:
                # 中国A股和港股：使用社交媒体情绪分析
                logger.info(f"🇨🇳🇭🇰 [统一情绪工具] 处理中文市场情绪...")

                try:
                    # 可以集成微博、雪球、东方财富等中文社交媒体情绪
                    # 目前使用基础的情绪分析
                    sentiment_summary = f"""
## 中文市场情绪分析

**股票**: {ticker} ({market_info['market_name']})
**分析日期**: {curr_date}

### 市场情绪概况
- 由于中文社交媒体情绪数据源暂未完全集成，当前提供基础分析
- 建议关注雪球、东方财富、同花顺等平台的讨论热度
- 港股市场还需关注香港本地财经媒体情绪

### 情绪指标
- 整体情绪: 中性
- 讨论热度: 待分析
- 投资者信心: 待评估

*注：完整的中文社交媒体情绪分析功能正在开发中*
"""
                    result_data.append(sentiment_summary)
                except Exception as e:
                    result_data.append(f"## 中文市场情绪\n获取失败: {e}")

            else:
                # 美股：使用Reddit情绪分析
                logger.info(f"🇺🇸 [统一情绪工具] 处理美股情绪...")

                try:
                    from tradingagents.dataflows.interface import get_reddit_sentiment

                    sentiment_data = get_reddit_sentiment(ticker, curr_date)
                    result_data.append(f"## 美股Reddit情绪\n{sentiment_data}")
                except Exception as e:
                    result_data.append(f"## 美股Reddit情绪\n获取失败: {e}")

            # 组合所有数据
            combined_result = f"""# {ticker} 情绪分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的情绪数据源*
"""

            logger.info(f"😊 [统一情绪工具] 数据获取完成，总长度: {len(combined_result)}")
            return combined_result

        except Exception as e:
            error_msg = f"统一情绪分析工具执行失败: {str(e)}"
            logger.error(f"❌ [统一情绪工具] {error_msg}")
            return error_msg

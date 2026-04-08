import request from './request'

export interface Strategy {
  id: string
  user_id: string
  name: string
  description: string
  market: string
  code: string
  created_at: string
  updated_at: string
  backtest_count: number
}

export interface BacktestRequest {
  start_date: string
  end_date: string
  initial_capital: number
}

export interface BacktestResult {
  success: boolean
  data?: {
    summary: {
      total_return: number
      sharpe_ratio: number
      max_drawdown: number
      win_rate: number
      total_trades: number
    }
    equity_curve: Array<{ date: string; value: number }>
    trades: Array<{
      date: string
      action: string
      symbol: string
      price: number
      quantity: number
      pnl?: number
    }>
  }
  message?: string
}

export const strategyApi = {
  // 获取策略列表
  getStrategies() {
    return request.get<Strategy[]>('/api/strategies')
  },

  // 创建策略
  createStrategy(data: {
    name: string
    description: string
    market: string
  }) {
    return request.post<Strategy>('/api/strategies/create', data)
  },

  // 运行回测
  runBacktest(strategyId: string, data: BacktestRequest) {
    return request.post<BacktestResult>(`/api/strategies/${strategyId}/backtest`, data)
  },

  // 删除策略
  deleteStrategy(strategyId: string) {
    return request.delete(`/api/strategies/${strategyId}`)
  }
}

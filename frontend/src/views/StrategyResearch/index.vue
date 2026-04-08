<template>
  <div class="strategy-research">
    <el-page-header @back="goBack" content="策略研究" style="margin-bottom: 20px" />

    <el-row :gutter="20">
      <!-- Left: Strategy List -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>我的策略</span>
              <el-button type="primary" size="small" @click="showCreateDialog = true">
                <el-icon><Plus /></el-icon> 建立策略
              </el-button>
            </div>
          </template>

          <el-empty v-if="strategies.length === 0" description="暂无策略，点击上方按钮创建">
            <el-button type="primary" @click="showCreateDialog = true">立即创建</el-button>
          </el-empty>

          <div v-else class="strategy-list">
            <div
              v-for="strategy in strategies"
              :key="strategy.id"
              class="strategy-item"
              :class="{ active: selectedStrategy?.id === strategy.id }"
              @click="selectStrategy(strategy)"
            >
              <div class="strategy-header">
                <h4>{{ strategy.name }}</h4>
                <el-tag :type="strategy.status === 'active' ? 'success' : 'info'" size="small">
                  {{ strategy.status === 'active' ? '已启用' : '未启用' }}
                </el-tag>
              </div>
              <p class="strategy-description">{{ strategy.description }}</p>
              <div class="strategy-meta">
                <span>
                  <el-icon><Calendar /></el-icon> {{ formatDate(strategy.created_at) }}
                </span>
                <span>
                  <el-icon><TrendCharts /></el-icon> {{ strategy.backtest_count || 0 }} 次回测
                </span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Right: Strategy Details & Backtest -->
      <el-col :span="16">
        <el-card v-if="!selectedStrategy" shadow="hover" style="min-height: 400px">
          <el-empty description="请从左侧选择一个策略" />
        </el-card>

        <div v-else>
          <!-- Strategy Info -->
          <el-card shadow="hover" style="margin-bottom: 20px">
            <template #header>
              <div class="card-header">
                <span>{{ selectedStrategy.name }}</span>
                <div>
                  <el-button size="small" @click="editStrategy">
                    <el-icon><Edit /></el-icon> 编辑
                  </el-button>
                  <el-button size="small" type="danger" @click="deleteStrategy">
                    <el-icon><Delete /></el-icon> 删除
                  </el-button>
                </div>
              </div>
            </template>

            <el-descriptions :column="2" border>
              <el-descriptions-item label="策略描述">{{ selectedStrategy.description }}</el-descriptions-item>
              <el-descriptions-item label="市场">{{ getMarketName(selectedStrategy.market) }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDate(selectedStrategy.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="最后更新">{{ formatDate(selectedStrategy.updated_at) }}</el-descriptions-item>
            </el-descriptions>

            <el-divider>策略代码</el-divider>
            <pre class="strategy-code"><code>{{ selectedStrategy.code }}</code></pre>
          </el-card>

          <!-- Backtest Section -->
          <el-card shadow="hover">
            <template #header>
              <div class="card-header">
                <span>📊 線上回測</span>
                <el-button type="primary" @click="showBacktestDialog = true" :loading="backtesting">
                  <el-icon><VideoPlay /></el-icon> 開始回測
                </el-button>
              </div>
            </template>

            <!-- Backtest Results -->
            <div v-if="backtestResults">
              <el-alert
                :title="`回測完成 - 總收益率: ${backtestResults.total_return_pct.toFixed(2)}%`"
                :type="backtestResults.total_return_pct > 0 ? 'success' : 'error'"
                :closable="false"
                style="margin-bottom: 20px"
              />

              <el-row :gutter="20" style="margin-bottom: 20px">
                <el-col :span="6">
                  <el-statistic title="起始資金" :value="backtestResults.initial_capital" :precision="2" prefix="¥" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="最終資金" :value="backtestResults.final_capital" :precision="2" prefix="¥" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="總收益" :value="backtestResults.total_return" :precision="2" prefix="¥" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="收益率" :value="backtestResults.total_return_pct" :precision="2" suffix="%" />
                </el-col>
              </el-row>

              <el-row :gutter="20" style="margin-bottom: 20px">
                <el-col :span="6">
                  <el-statistic title="夏普比率" :value="backtestResults.sharpe_ratio" :precision="3" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="最大回撤" :value="backtestResults.max_drawdown" :precision="2" suffix="%" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="交易次數" :value="backtestResults.total_trades" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="勝率" :value="backtestResults.win_rate" :precision="2" suffix="%" />
                </el-col>
              </el-row>

              <!-- Equity Curve Chart -->
              <div ref="equityChart" style="width: 100%; height: 400px"></div>

              <!-- Trade History -->
              <el-divider>交易記錄</el-divider>
              <el-table :data="backtestResults.trades" size="small" max-height="300">
                <el-table-column prop="date" label="日期" width="120" />
                <el-table-column prop="action" label="操作" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.action === 'buy' ? 'success' : 'danger'" size="small">
                      {{ row.action === 'buy' ? '買入' : '賣出' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="code" label="股票代碼" width="100" />
                <el-table-column prop="price" label="價格" width="100" />
                <el-table-column prop="quantity" label="數量" width="100" />
                <el-table-column prop="amount" label="金額" width="120" />
                <el-table-column prop="pnl" label="盈虧" width="120">
                  <template #default="{ row }">
                    <span :style="{ color: row.pnl > 0 ? '#67C23A' : '#F56C6C' }">
                      {{ row.pnl > 0 ? '+' : '' }}{{ row.pnl?.toFixed(2) || '-' }}
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <el-empty v-else description="配置回測參數並開始回測，查看策略表現" />
          </el-card>
        </div>
      </el-col>
    </el-row>

    <!-- Create Strategy Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      title="建立策略"
      width="60%"
      :close-on-click-modal="false"
    >
      <el-form :model="newStrategy" label-width="100px">
        <el-form-item label="策略名稱" required>
          <el-input v-model="newStrategy.name" placeholder="例如：RSI均值回归策略" />
        </el-form-item>

        <el-form-item label="市場" required>
          <el-select v-model="newStrategy.market" placeholder="選擇市場">
            <el-option label="🇨🇳 A股" value="CN" />
            <el-option label="🇹🇼 台股" value="TW" />
            <el-option label="🇭🇰 港股" value="HK" />
            <el-option label="🇺🇸 美股" value="US" />
          </el-select>
        </el-form-item>

        <el-form-item label="策略描述">
          <el-input
            v-model="newStrategy.prompt"
            type="textarea"
            :rows="4"
            placeholder="請用自然語言描述您的策略，例如：&#10;當股票的RSI指標小於30時買入，大於70時賣出。&#10;只買入市值排名前50的股票。&#10;每次交易使用可用資金的20%。"
          />
        </el-form-item>

        <el-alert
          title="💡 提示"
          type="info"
          :closable="false"
          style="margin-bottom: 20px"
        >
          AI 將根據您的描述自動生成策略代碼，您也可以稍後手動修改。
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createStrategy" :loading="creating">
          <el-icon><MagicStick /></el-icon> 生成策略
        </el-button>
      </template>
    </el-dialog>

    <!-- Backtest Config Dialog -->
    <el-dialog
      v-model="showBacktestDialog"
      title="配置回測參數"
      width="50%"
      :close-on-click-modal="false"
    >
      <el-form :model="backtestConfig" label-width="120px">
        <el-form-item label="起始日期" required>
          <el-date-picker
            v-model="backtestConfig.start_date"
            type="date"
            placeholder="選擇日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>

        <el-form-item label="結束日期" required>
          <el-date-picker
            v-model="backtestConfig.end_date"
            type="date"
            placeholder="選擇日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>

        <el-form-item label="初始資金" required>
          <el-input-number
            v-model="backtestConfig.initial_capital"
            :min="10000"
            :max="100000000"
            :step="10000"
            controls-position="right"
          />
        </el-form-item>

        <el-form-item label="手續費率">
          <el-input-number
            v-model="backtestConfig.commission_rate"
            :min="0"
            :max="0.01"
            :step="0.0001"
            :precision="4"
            controls-position="right"
          />
          <span style="margin-left: 10px; color: #909399">例如: 0.0003 = 0.03%</span>
        </el-form-item>

        <el-form-item label="滑點">
          <el-input-number
            v-model="backtestConfig.slippage"
            :min="0"
            :max="0.01"
            :step="0.0001"
            :precision="4"
            controls-position="right"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showBacktestDialog = false">取消</el-button>
        <el-button type="primary" @click="runBacktest" :loading="backtesting">
          開始回測
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Calendar, TrendCharts, Edit, Delete, VideoPlay, MagicStick } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { strategyApi } from '@/api/strategy'

const router = useRouter()

// State
const strategies = ref([])
const selectedStrategy = ref(null)
const showCreateDialog = ref(false)
const showBacktestDialog = ref(false)
const creating = ref(false)
const backtesting = ref(false)
const backtestResults = ref(null)
const equityChart = ref(null)

// Forms
const newStrategy = ref({
  name: '',
  market: 'CN',
  prompt: ''
})

const backtestConfig = ref({
  start_date: '2025-10-01',
  end_date: '2026-03-31',
  initial_capital: 1000000,
  commission_rate: 0.0003,
  slippage: 0.0001
})

// Methods
const goBack = () => {
  router.back()
}

const loadStrategies = async () => {
  try {
    const res = await strategyApi.getStrategies()
    if (res.data.success) {
      strategies.value = res.data.data || []
    }
  } catch (error) {
    console.error('加載策略失敗:', error)
  }
}

const selectStrategy = (strategy) => {
  selectedStrategy.value = strategy
  backtestResults.value = null
}

const createStrategy = async () => {
  if (!newStrategy.value.name || !newStrategy.value.prompt) {
    ElMessage.warning('請填寫策略名稱和描述')
    return
  }

  creating.value = true
  try {
    const res = await strategyApi.createStrategy({
      name: newStrategy.value.name,
      market: newStrategy.value.market,
      description: newStrategy.value.prompt
    })

    if (res.data.success) {
      ElMessage.success('策略創建成功！')
      showCreateDialog.value = false
      newStrategy.value = { name: '', market: 'CN', prompt: '' }
      await loadStrategies()
      selectedStrategy.value = res.data.data
    } else {
      ElMessage.error(res.data.message || '創建失敗')
    }
  } catch (error) {
    console.error('創建策略失敗:', error)
    ElMessage.error('創建失敗，請重試')
  } finally {
    creating.value = false
  }
}

const editStrategy = () => {
  ElMessage.info('編輯功能開發中...')
}

const deleteStrategy = async () => {
  try {
    await ElMessageBox.confirm('確定要刪除此策略嗎？', '警告', {
      confirmButtonText: '確定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const res = await strategyApi.deleteStrategy(selectedStrategy.value.id)
    if (res.data.success) {
      ElMessage.success('刪除成功')
      selectedStrategy.value = null
      await loadStrategies()
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('刪除失敗:', error)
      ElMessage.error('刪除失敗')
    }
  }
}

const runBacktest = async () => {
  if (!backtestConfig.value.start_date || !backtestConfig.value.end_date) {
    ElMessage.warning('請選擇回測日期範圍')
    return
  }

  backtesting.value = true
  try {
    const res = await strategyApi.runBacktest(selectedStrategy.value.id, {
      start_date: backtestConfig.value.start_date,
      end_date: backtestConfig.value.end_date,
      initial_capital: backtestConfig.value.initial_capital
    })

    if (res.data.success) {
      backtestResults.value = res.data.data
      showBacktestDialog.value = false
      ElMessage.success('回測完成！')
      
      // Render equity curve chart
      await nextTick()
      renderEquityChart()
    } else {
      ElMessage.error(res.data.message || '回測失敗')
    }
  } catch (error) {
    console.error('回測失敗:', error)
    ElMessage.error('回測失敗，請重試')
  } finally {
    backtesting.value = false
  }
}

const renderEquityChart = () => {
  if (!equityChart.value || !backtestResults.value) return

  const chart = echarts.init(equityChart.value)
  
  const option = {
    title: {
      text: '資金曲線'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['總資產']
    },
    xAxis: {
      type: 'category',
      data: backtestResults.value.equity_curve.dates
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '¥{value}'
      }
    },
    series: [
      {
        name: '總資產',
        type: 'line',
        data: backtestResults.value.equity_curve.values,
        smooth: true,
        itemStyle: {
          color: '#67C23A'
        }
      }
    ]
  }

  chart.setOption(option)
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const getMarketName = (market) => {
  const marketMap = {
    CN: '🇨🇳 A股',
    TW: '🇹🇼 台股',
    HK: '🇭🇰 港股',
    US: '🇺🇸 美股'
  }
  return marketMap[market] || market
}

onMounted(() => {
  loadStrategies()
})
</script>

<style scoped>
.strategy-research {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.strategy-list {
  max-height: 600px;
  overflow-y: auto;
}

.strategy-item {
  padding: 15px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.3s;
}

.strategy-item:hover {
  border-color: #409eff;
  background-color: #f0f9ff;
}

.strategy-item.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.strategy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.strategy-header h4 {
  margin: 0;
  font-size: 16px;
}

.strategy-description {
  margin: 0 0 10px 0;
  color: #606266;
  font-size: 14px;
}

.strategy-meta {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: #909399;
}

.strategy-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.strategy-code {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
}

.strategy-code code {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}
</style>

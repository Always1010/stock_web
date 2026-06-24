<template>
  <div v-loading="loading">
    <div class="page-header">
      <div>
        <h2>{{ portfolio.name }}</h2>
        <span class="code">{{ portfolio.code }}</span>
      </div>
      <div class="nav-summary">
        <div>
          <span class="label">最新净值</span>
          <span class="value">¥{{ portfolio.latest_nav != null ? portfolio.latest_nav.toFixed(2) : '--' }}</span>
        </div>
        <div>
          <span class="label">累计收益率</span>
          <span :class="['value', portfolio.latest_return_rate >= 0 ? 'up' : 'down']">
            {{ portfolio.latest_return_rate != null ? (portfolio.latest_return_rate * 100).toFixed(2) + '%' : '--' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Holdings Table -->
    <el-card style="margin-bottom:20px">
      <template #header>
        <div class="card-header">
          <span>持仓明细</span>
          <el-button type="primary" size="small" @click="showAddHolding = true">添加股票</el-button>
        </div>
      </template>
      <el-table :data="portfolio.holdings" border stripe empty-text="暂无持仓">
        <el-table-column prop="stock_code" label="代码" width="100" />
        <el-table-column prop="stock_name" label="名称" width="140" />
        <el-table-column label="持仓股数" width="120">
          <template #default="{ row }">
            <span>{{ row.shares }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成本价" width="120">
          <template #default="{ row }">
            {{ row.cost_price != null ? '¥' + row.cost_price.toFixed(3) : '未设定' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <el-button v-if="!row.is_cost_locked" size="small" @click="openSetCost(row)">设定成本</el-button>
            <el-tag v-else size="small" type="info">成本已锁定</el-tag>
            <el-button size="small" type="danger" style="margin-left:8px" @click="handleRemove(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Charts -->
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="收益曲线" name="curve">
        <div ref="curveRef" style="width:100%;height:400px"></div>
        <div style="margin-top:12px">
          <el-radio-group v-model="chartRange" @change="renderCurve" size="small">
            <el-radio-button value="1m">1月</el-radio-button>
            <el-radio-button value="3m">3月</el-radio-button>
            <el-radio-button value="6m">6月</el-radio-button>
            <el-radio-button value="1y">1年</el-radio-button>
            <el-radio-button value="all">全部</el-radio-button>
          </el-radio-group>
        </div>
      </el-tab-pane>

      <el-tab-pane label="收益日历" name="heatmap">
        <div style="margin-bottom:12px">
          <span>年份：</span>
          <el-select v-model="heatmapYear" @change="renderHeatmap" size="small">
            <el-option v-for="y in years" :key="y" :label="String(y)" :value="y" />
          </el-select>
        </div>
        <div ref="heatmapRef" style="width:100%;height:220px"></div>
      </el-tab-pane>

      <el-tab-pane label="贡献分析" name="contribution">
        <div ref="contribRef" style="width:100%;height:400px"></div>
      </el-tab-pane>
    </el-tabs>

    <!-- Add Holding Dialog -->
    <el-dialog v-model="showAddHolding" title="添加股票到组合" width="450px">
      <el-form :model="addForm" label-position="top">
        <el-form-item label="股票代码">
          <el-input v-model="addForm.stock_code" placeholder="例如：600519" />
        </el-form-item>
        <el-form-item label="持仓股数">
          <el-input-number v-model="addForm.shares" :min="1" :step="100" style="width:100%" />
        </el-form-item>
        <el-form-item label="成本价（可选，不填则自动计算）">
          <el-input-number v-model="addForm.cost_price" :min="0" :step="0.01" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddHolding = false">取消</el-button>
        <el-button type="primary" @click="handleAddHolding">确定</el-button>
      </template>
    </el-dialog>

    <!-- Set Cost Dialog -->
    <el-dialog v-model="showSetCost" title="设定成本价" width="350px">
      <el-form-item label="成本价（设定后不可修改）">
        <el-input-number v-model="costForm.cost_price" :min="0" :step="0.01" style="width:100%" />
      </el-form-item>
      <template #footer>
        <el-button @click="showSetCost = false">取消</el-button>
        <el-button type="primary" @click="handleSetCost">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { portfolioApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const code = route.params.code

const loading = ref(false)
const portfolio = ref({ name: '', code: '', holdings: [], latest_nav: null, latest_return_rate: null })
const activeTab = ref('curve')
const chartRange = ref('6m')

// Add holding dialog
const showAddHolding = ref(false)
const addForm = ref({ stock_code: '', shares: 100, cost_price: null })

// Set cost dialog
const showSetCost = ref(false)
const costForm = ref({ holding_id: null, cost_price: 0 })

// Charts
const curveRef = ref(null)
const heatmapRef = ref(null)
const contribRef = ref(null)
let curveChart = null, heatmapChart = null, contribChart = null
const heatmapYear = ref(new Date().getFullYear())
const years = ref([])

async function fetchPortfolio() {
  loading.value = true
  try {
    const { data } = await portfolioApi.detail(code)
    portfolio.value = data
  } finally {
    loading.value = false
  }
}

// ── Holdings ──
async function handleAddHolding() {
  try {
    await portfolioApi.addHolding(code, {
      stock_code: addForm.value.stock_code,
      shares: addForm.value.shares,
      cost_price: addForm.value.cost_price || null,
    })
    ElMessage.success('添加成功')
    showAddHolding.value = false
    addForm.value = { stock_code: '', shares: 100, cost_price: null }
    fetchPortfolio()
  } catch (e) { /* handled */ }
}

function openSetCost(row) {
  costForm.value = { holding_id: row.id, cost_price: row.cost_price || 0 }
  showSetCost.value = true
}

async function handleSetCost() {
  try {
    await portfolioApi.setCost(code, costForm.value.holding_id, {
      cost_price: costForm.value.cost_price,
    })
    ElMessage.success('成本价已设定')
    showSetCost.value = false
    fetchPortfolio()
  } catch (e) { /* handled */ }
}

async function handleRemove(row) {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.stock_name}？`, '确认删除')
    await portfolioApi.removeHolding(code, row.id)
    ElMessage.success('已删除')
    fetchPortfolio()
  } catch (e) { /* cancelled or handled */ }
}

// ── Curve Chart ──
function getDateRange() {
  const today = new Date()
  const end = today.toISOString().slice(0, 10)
  const map = { '1m': 30, '3m': 90, '6m': 180, '1y': 365, all: 3650 }
  const start = new Date(today.getTime() - map[chartRange.value] * 86400000).toISOString().slice(0, 10)
  return { start, end }
}

async function renderCurve() {
  const { start, end } = getDateRange()
  const { data: res } = await portfolioApi.nav(code, start, end)

  if (!curveChart && curveRef.value) {
    curveChart = echarts.init(curveRef.value)
  }
  if (!curveChart) return

  const dates = res.data.map(d => d.date)
  const vals = res.data.map(d => d.cum_return_rate != null ? (d.cum_return_rate * 100).toFixed(2) : null)

  curveChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [{
      name: '累计收益率',
      type: 'line',
      data: vals,
      smooth: true,
      areaStyle: { opacity: 0.1 },
      markLine: { data: [{ yAxis: 0 }], lineStyle: { color: '#909399', type: 'dashed' } },
    }],
  }, true)
}

// ── Heatmap ──
async function renderHeatmap() {
  const { data: res } = await portfolioApi.dailyReturns(code, heatmapYear.value)
  const data = res.data.map(d => [d.date, d.return_rate != null ? +(d.return_rate * 100).toFixed(2) : 0])

  if (!heatmapChart && heatmapRef.value) {
    heatmapChart = echarts.init(heatmapRef.value)
  }
  if (!heatmapChart) return

  heatmapChart.setOption({
    tooltip: {
      formatter: p => `${p.data[0]}<br/>收益率: ${p.data[1]}%`,
    },
    visualMap: {
      min: -10, max: 10,
      inRange: { color: ['#67c23a', '#fff', '#f56c6c'] },
      show: false,
    },
    calendar: {
      range: String(heatmapYear.value),
      cellSize: ['auto', 16],
      dayLabel: { nameMap: 'ZH' },
      monthLabel: { nameMap: 'ZH' },
    },
    series: [{
      type: 'heatmap',
      coordinateSystem: 'calendar',
      data: data,
    }],
  }, true)
}

// ── Contribution Chart ──
async function renderContribution() {
  const { data: res } = await portfolioApi.contributions(code)

  if (!contribChart && contribRef.value) {
    contribChart = echarts.init(contribRef.value)
  }
  if (!contribChart) return

  const names = res.data.map(d => d.stock_name)
  const values = res.data.map(d => d.return_amount != null ? d.return_amount : 0)
  const colors = values.map(v => v >= 0 ? '#f56c6c' : '#67c23a')

  contribChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', axisLabel: { formatter: '¥{value}' } },
    yAxis: { type: 'category', data: names },
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
      label: { show: true, position: 'right', formatter: p => '¥' + p.value.toFixed(2) },
    }],
  }, true)
}

onMounted(async () => {
  await fetchPortfolio()
  await nextTick()
  renderCurve()
  renderContribution()

  const now = new Date()
  for (let y = now.getFullYear(); y >= now.getFullYear() - 3; y--) {
    years.value.push(y)
  }
  heatmapYear.value = now.getFullYear()
  await nextTick()
  renderHeatmap()
})

const handleResize = () => {
  curveChart?.resize()
  heatmapChart?.resize()
  contribChart?.resize()
}
window.addEventListener('resize', handleResize)

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  curveChart?.dispose()
  heatmapChart?.dispose()
  contribChart?.dispose()
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.code { color: #909399; font-size: 13px; }
.nav-summary { text-align: right; }
.nav-summary .label { display: block; font-size: 12px; color: #909399; }
.nav-summary .value { font-size: 22px; font-weight: bold; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>

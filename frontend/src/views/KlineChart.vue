<template>
  <div>
    <!-- Price Hero -->
    <div class="kline-hero" v-if="latestData">
      <div class="hero-left">
        <div class="hero-name">{{ stockName }}</div>
        <div class="hero-code">{{ code }}</div>
      </div>
      <div class="hero-right">
        <div class="hero-price" :class="priceColor">
          {{ latestData.close.toFixed(2) }}
        </div>
        <div class="hero-change" v-if="latestChange != null" :class="priceColor">
          {{ latestChange >= 0 ? '+' : '' }}{{ latestChange.toFixed(2) }} ({{ latestChangePct >= 0 ? '+' : '' }}{{ latestChangePct.toFixed(2) }}%)
        </div>
        <div class="hero-change" v-else style="color:var(--color-text-muted)">--</div>
      </div>
    </div>

    <!-- Detail row -->
    <div class="kline-detail-row" v-if="latestData">
      <div class="detail-item">
        <span class="detail-label">开盘</span>
        <span class="detail-value">{{ latestData.open.toFixed(2) }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">最高</span>
        <span class="detail-value" :class="latestData.high > latestData.open ? 'up' : ''">{{ latestData.high.toFixed(2) }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">最低</span>
        <span class="detail-value" :class="latestData.low < latestData.open ? 'down' : ''">{{ latestData.low.toFixed(2) }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">成交额</span>
        <span class="detail-value">{{ fmtAmount(latestData.amount) }}</span>
      </div>
      <button class="hero-star" @click="addWatchlist">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        加自选
      </button>
    </div>

    <!-- Range bar -->
    <div class="range-bar">
      <button v-for="r in ranges" :key="r.key" class="range-btn" :class="{ active: range === r.key }" @click="range=r.key;fetchData()">{{ r.label }}</button>
    </div>

    <!-- Chart -->
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { stockApi, watchlistApi } from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const code = route.params.code
const stockName = ref('')
const range = ref('6m')
const chartRef = ref(null)
let chart = null
const klineData = ref([])

const ranges = [
  { key: '1m', label: '1月' }, { key: '3m', label: '3月' }, { key: '6m', label: '6月' },
  { key: '1y', label: '1年' }, { key: 'all', label: '全部' },
]

const latestData = computed(() => klineData.value.length ? klineData.value[klineData.value.length - 1] : null)
const latestChange = computed(() => latestData.value && klineData.value.length >= 2 ? latestData.value.close - klineData.value[klineData.value.length - 2].close : null)
const latestChangePct = computed(() => {
  if (!latestChange.value || klineData.value.length < 2) return null
  const prev = klineData.value[klineData.value.length - 2].close
  return prev ? (latestChange.value / prev * 100) : null
})
const priceColor = computed(() => {
  if (latestChange.value == null) return ''
  if (latestChange.value > 0) return 'up'
  if (latestChange.value < 0) return 'down'
  return ''
})

function fmtAmount(v) {
  if (!v || v === 0) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
  return v.toString()
}

function getDateRange() {
  const today = new Date()
  const end = today.toISOString().slice(0, 10)
  const map = { '1m': 30, '3m': 90, '6m': 180, '1y': 365, all: 3650 }
  return { start: new Date(today.getTime() - map[range.value] * 86400000).toISOString().slice(0, 10), end }
}

function calcMA(data, period) {
  const r = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { r.push(null); continue }
    let s = 0; for (let j = 0; j < period; j++) s += data[i - j][4]
    r.push(+(s / period).toFixed(2))
  }
  return r
}

async function fetchData() {
  const { start, end } = getDateRange()
  const { data: res } = await stockApi.kline(code, start, end)
  stockName.value = res.name
  klineData.value = res.data
  if (!res.data.length) return

  const dates = res.data.map(d => d.date)
  const ohlc = res.data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = res.data.map(d => d.volume)

  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption({
    backgroundColor: '#fff',
    grid: [
      { left: '10%', right: '10%', top: 20, height: '58%' },
      { left: '10%', right: '10%', top: '78%', height: '15%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLine: { lineStyle: { color: '#e5e7eb' } }, axisTick: { show: false }, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, axisLine: { lineStyle: { color: '#e5e7eb' } }, axisTick: { show: false }, axisLabel: { color: '#9ca3af', fontSize: 10 } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: '#f3f4f6' } }, axisLabel: { color: '#9ca3af', fontSize: 10 } },
      { type: 'value', gridIndex: 1, splitLine: { show: false }, axisLabel: { color: '#9ca3af', fontSize: 10, formatter: v => v >= 1e8 ? (v/1e8).toFixed(1)+'亿' : (v/1e4).toFixed(0)+'万' } },
    ],
    series: [
      { name: 'K线', type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0, itemStyle: { color: '#e15241', color0: '#1aad56', borderColor: '#e15241', borderColor0: '#1aad56' } },
      { name: 'MA5', type: 'line', data: calcMA(res.data, 5), xAxisIndex: 0, yAxisIndex: 0, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'MA10', type: 'line', data: calcMA(res.data, 10), xAxisIndex: 0, yAxisIndex: 0, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#3b82f6' } },
      { name: 'MA20', type: 'line', data: calcMA(res.data, 20), xAxisIndex: 0, yAxisIndex: 0, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#8b5cf6' } },
      { name: '量', type: 'bar', data: volumes.map((v, i) => ({ value: v, itemStyle: { color: i > 0 && ohlc[i] ? (ohlc[i][1] >= ohlc[i-1][1] ? '#e15241' : '#1aad56') : '#e15241', opacity: 0.5 } })), xAxisIndex: 1, yAxisIndex: 1 },
    ],
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, backgroundColor: '#fff', borderColor: '#e5e7eb', textStyle: { color: '#1e2130', fontSize: 12 } },
  }, true)
}

function addWatchlist() { watchlistApi.add(code).then(() => ElMessage.success('已添加到自选')) }

onMounted(fetchData)
const hr = () => chart?.resize()
window.addEventListener('resize', hr)
onUnmounted(() => { window.removeEventListener('resize', hr); chart?.dispose() })
</script>

<style scoped>
/* ── Hero ── */
.kline-hero {
  display: flex; justify-content: space-between; align-items: center;
  background: var(--color-surface); border-radius: var(--radius-lg);
  padding: var(--space-5) var(--space-6); margin-bottom: var(--space-4);
  box-shadow: var(--shadow-sm);
}
.hero-name { font-size: var(--text-lg); font-weight: 600; }
.hero-code { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--color-text-muted); margin-top: 2px; }
.hero-right { text-align: right; }
.hero-price { font-family: var(--font-mono); font-size: 32px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.2; }
.hero-price.up { color: var(--color-up); }
.hero-price.down { color: var(--color-down); }
.hero-change { font-size: var(--text-sm); margin-top: 2px; }
.hero-change.up { color: var(--color-up); }
.hero-change.down { color: var(--color-down); }

/* ── Detail row ── */
.kline-detail-row {
  display: flex; align-items: center; gap: var(--space-6);
  background: var(--color-surface); border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-6); margin-bottom: var(--space-4);
  box-shadow: var(--shadow-sm);
}
.detail-item { display: flex; flex-direction: column; gap: 2px; }
.detail-label { font-size: 10px; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.detail-value { font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 600; font-variant-numeric: tabular-nums; }
.detail-value.up { color: var(--color-up); }
.detail-value.down { color: var(--color-down); }
.hero-star {
  margin-left: auto; display: inline-flex; align-items: center; gap: 5px;
  height: 32px; padding: 0 var(--space-3); border: 1px solid var(--color-border);
  background: transparent; border-radius: var(--radius-sm); font-size: var(--text-xs);
  font-weight: 500; cursor: pointer; font-family: inherit; color: var(--color-text-secondary);
  transition: all var(--transition-fast);
}
.hero-star:hover { border-color: var(--color-primary); color: var(--color-primary); background: var(--color-primary-light); }

/* ── Range ── */
.range-bar { display: flex; gap: 4px; background: var(--color-bg); padding: 4px; border-radius: var(--radius-sm); width: fit-content; margin-bottom: var(--space-4); }
.range-btn { padding: 6px 16px; border: none; background: transparent; border-radius: 6px; font-size: var(--text-sm); color: var(--color-text-secondary); cursor: pointer; font-family: inherit; font-weight: 500; transition: all var(--transition-fast); }
.range-btn.active { background: var(--color-surface); color: var(--color-text-primary); box-shadow: var(--shadow-sm); }
.range-btn:hover:not(.active) { color: var(--color-text-primary); }

.chart-container { width: 100%; height: 540px; background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); padding: var(--space-3); }
</style>

<template>
  <div>
    <div class="kline-top">
      <div>
        <h1 class="page-title" style="margin-bottom:2px">{{ stockName }}</h1>
        <span class="stock-code">{{ code }}</span>
      </div>
      <button class="btn-star" @click="addWatchlist">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        加自选
      </button>
    </div>

    <div class="range-bar">
      <button v-for="r in ranges" :key="r.key" class="range-btn" :class="{ active: range === r.key }" @click="range=r.key;fetchData()">
        {{ r.label }}
      </button>
    </div>

    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
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

const ranges = [
  { key: '1m', label: '1月' },
  { key: '3m', label: '3月' },
  { key: '6m', label: '6月' },
  { key: '1y', label: '1年' },
  { key: 'all', label: '全部' },
]

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
      {
        name: 'K线', type: 'candlestick', data: ohlc,
        xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: '#e15241', color0: '#1aad56', borderColor: '#e15241', borderColor0: '#1aad56' },
      },
      { name: 'MA5', type: 'line', data: calcMA(res.data, 5), xAxisIndex: 0, yAxisIndex: 0, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'MA10', type: 'line', data: calcMA(res.data, 10), xAxisIndex: 0, yAxisIndex: 0, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#3b82f6' } },
      { name: 'MA20', type: 'line', data: calcMA(res.data, 20), xAxisIndex: 0, yAxisIndex: 0, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#8b5cf6' } },
      {
        name: '量', type: 'bar', data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: i > 0 && ohlc[i] ? (ohlc[i][1] >= ohlc[i - 1][1] ? '#e15241' : '#1aad56') : '#e15241', opacity: 0.5 },
        })),
        xAxisIndex: 1, yAxisIndex: 1,
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#fff',
      borderColor: '#e5e7eb',
      textStyle: { color: '#1e2130', fontSize: 12 },
      formatter(ps) {
        if (!ps || !ps.length) return ''
        const d = ps[0].data
        return `<div style="font-weight:600;margin-bottom:4px">${ps[0].axisValue}</div>
          开 ${d[1]}<br/>收 ${d[2]}<br/>低 ${d[3]}<br/>高 ${d[4]}`
      },
    },
  }, true)
}

function addWatchlist() {
  watchlistApi.add(code).then(() => ElMessage.success('已添加到自选'))
}

onMounted(fetchData)
const hr = () => chart?.resize()
window.addEventListener('resize', hr)
onUnmounted(() => { window.removeEventListener('resize', hr); chart?.dispose() })
</script>

<style scoped>
.kline-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-4);
}
.stock-code {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 2px 8px;
  border-radius: 4px;
}
.btn-star {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 var(--space-4);
  background: var(--color-primary-light);
  color: var(--color-primary);
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: all var(--transition-fast);
}
.btn-star:hover { background: #dbeafe; }

.range-bar {
  display: flex;
  gap: 4px;
  background: var(--color-bg);
  padding: 4px;
  border-radius: var(--radius-sm);
  width: fit-content;
  margin-bottom: var(--space-4);
}
.range-btn {
  padding: 6px 16px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  transition: all var(--transition-fast);
}
.range-btn.active {
  background: var(--color-surface);
  color: var(--color-text-primary);
  box-shadow: var(--shadow-sm);
}
.range-btn:hover:not(.active) { color: var(--color-text-primary); }

.chart-container {
  width: 100%;
  height: 540px;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-3);
}
</style>

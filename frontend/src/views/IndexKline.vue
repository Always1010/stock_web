<template>
  <div>
    <div class="kline-top">
      <div>
        <div class="back-link" @click="$router.push('/market')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
          返回行情
        </div>
        <h1 class="page-title" style="margin-bottom:2px">{{ idxName }}</h1>
        <span class="stock-code">{{ idxCode }}</span>
      </div>
    </div>

    <div class="range-bar">
      <button v-for="r in ranges" :key="r.key" :class="['range-btn', { active: range === r.key }]" @click="range=r.key;fetchData()">{{ r.label }}</button>
    </div>

    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import api from '../api'

const route = useRoute()
const idxCode = route.params.code
const idxName = ref('')
const range = ref('6m')
const chartRef = ref(null)
let chart = null

const ranges = [
  { key: '1m', label: '1月' }, { key: '3m', label: '3月' },
  { key: '6m', label: '6月' }, { key: '1y', label: '1年' }, { key: 'all', label: '全部' },
]

function getDateRange() {
  const today = new Date()
  const end = today.toISOString().slice(0, 10)
  const map = { '1m': 30, '3m': 90, '6m': 180, '1y': 365, all: 3650 }
  return { start: new Date(today.getTime() - map[range.value] * 86400000).toISOString().slice(0, 10), end }
}

async function fetchData() {
  const { start, end } = getDateRange()
  const { data: res } = await api.get(`/market/indices/${idxCode}/kline`, { params: { start, end } })
  idxName.value = res.name
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
        type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: '#e15241', color0: '#1aad56', borderColor: '#e15241', borderColor0: '#1aad56' },
      },
      {
        type: 'bar', data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: i > 0 && ohlc[i] ? (ohlc[i][1] >= ohlc[i-1][1] ? '#e15241' : '#1aad56') : '#e15241', opacity: 0.5 },
        })),
        xAxisIndex: 1, yAxisIndex: 1,
      },
    ],
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'cross' },
      backgroundColor: '#fff', borderColor: '#e5e7eb',
      textStyle: { color: '#1e2130', fontSize: 12 },
    },
  }, true)
}

onMounted(fetchData)
const hr = () => chart?.resize()
window.addEventListener('resize', hr)
onUnmounted(() => { window.removeEventListener('resize', hr); chart?.dispose() })
</script>

<style scoped>
.kline-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--space-4); }
.back-link { display: inline-flex; align-items: center; gap: 4px; font-size: var(--text-sm); color: var(--color-text-secondary); cursor: pointer; margin-bottom: var(--space-2); }
.back-link:hover { color: var(--color-primary); }
.stock-code { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--color-text-secondary); background: var(--color-bg); padding: 2px 8px; border-radius: 4px; }
.range-bar { display: flex; gap: 4px; background: var(--color-bg); padding: 4px; border-radius: var(--radius-sm); width: fit-content; margin-bottom: var(--space-4); }
.range-btn { padding: 6px 16px; border: none; background: transparent; border-radius: 6px; font-size: var(--text-sm); color: var(--color-text-secondary); cursor: pointer; font-family: inherit; font-weight: 500; transition: all var(--transition-fast); }
.range-btn.active { background: var(--color-surface); color: var(--color-text-primary); box-shadow: var(--shadow-sm); }
.range-btn:hover:not(.active) { color: var(--color-text-primary); }
.chart-container { width: 100%; height: 540px; background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); padding: var(--space-3); }
</style>

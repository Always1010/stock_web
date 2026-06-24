<template>
  <div>
    <div class="kline-header">
      <h2>{{ stockName }} ({{ code }})</h2>
      <el-button @click="addWatchlist">⭐ 加自选</el-button>
    </div>

    <div style="margin-bottom:12px">
      <el-radio-group v-model="range" @change="fetchData" size="small">
        <el-radio-button value="1m">1月</el-radio-button>
        <el-radio-button value="3m">3月</el-radio-button>
        <el-radio-button value="6m">6月</el-radio-button>
        <el-radio-button value="1y">1年</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <div ref="chartRef" style="width:100%;height:550px"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
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

function getDateRange() {
  const today = new Date()
  const end = today.toISOString().slice(0, 10)
  const map = { '1m': 30, '3m': 90, '6m': 180, '1y': 365, all: 3650 }
  const start = new Date(today.getTime() - map[range.value] * 86400000).toISOString().slice(0, 10)
  return { start, end }
}

function calcMA(data, period) {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { result.push(null); continue }
    let sum = 0
    for (let j = 0; j < period; j++) sum += data[i - j][4]
    result.push(+(sum / period).toFixed(2))
  }
  return result
}

async function fetchData() {
  const { start, end } = getDateRange()
  const { data: res } = await stockApi.kline(code, start, end)
  stockName.value = res.name

  const dates = res.data.map(d => d.date)
  const ohlc = res.data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = res.data.map(d => d.volume)
  const closes = res.data.map(d => d.close)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter(p) {
        if (!p || !p.length) return ''
        const d = p[0].data
        return `${p[0].axisValue}<br/>
          开: ${d[1]}<br/>收: ${d[2]}<br/>低: ${d[3]}<br/>高: ${d[4]}`
      },
    },
    grid: [
      { left: '8%', right: '8%', top: 20, height: '60%' },
      { left: '8%', right: '8%', top: '72%', height: '20%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1 },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true },
      { type: 'value', gridIndex: 1 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#f56c6c',
          color0: '#67c23a',
          borderColor: '#f56c6c',
          borderColor0: '#67c23a',
        },
      },
      {
        name: 'MA5', type: 'line', data: calcMA(res.data, 5),
        xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, lineStyle: { width: 1 }, symbol: 'none',
      },
      {
        name: 'MA10', type: 'line', data: calcMA(res.data, 10),
        xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, lineStyle: { width: 1 }, symbol: 'none',
      },
      {
        name: 'MA20', type: 'line', data: calcMA(res.data, 20),
        xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, lineStyle: { width: 1 }, symbol: 'none',
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes.map((v, i) => {
          const up = i > 0 ? closes[i] >= closes[i - 1] : true
          return { value: v, itemStyle: { color: up ? '#f56c6c' : '#67c23a' } }
        }),
        xAxisIndex: 1,
        yAxisIndex: 1,
      },
    ],
  }

  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  chart.setOption(option, true)
}

function addWatchlist() {
  watchlistApi.add(code).then(() => ElMessage.success('已添加到自选'))
}

onMounted(() => fetchData())

const handleResize = () => chart?.resize()
window.addEventListener('resize', handleResize)

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<style scoped>
.kline-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
</style>

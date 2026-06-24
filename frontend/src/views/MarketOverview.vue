<template>
  <div>
    <h1 class="page-title">市场行情</h1>
    <p class="page-subtitle">数据更新于交易日 15:05</p>

    <!-- Index Cards -->
    <div class="index-grid">
      <div v-for="idx in indices" :key="idx.code" class="index-card" :class="{ up: idx.change >= 0, down: idx.change < 0 }" @click="$router.push(`/market/indices/${idx.code}`)" style="cursor:pointer">
        <div class="idx-name">{{ idx.name }}</div>
        <div class="idx-close">{{ idx.close.toFixed(2) }}</div>
        <div class="idx-change">
          <span class="idx-chg-val">{{ idx.change >= 0 ? '+' : '' }}{{ idx.change.toFixed(2) }}</span>
          <span class="idx-chg-pct">({{ idx.change_pct >= 0 ? '+' : '' }}{{ idx.change_pct.toFixed(2) }}%)</span>
        </div>
        <div class="idx-detail">
          <span>开 {{ idx.open.toFixed(2) }}</span>
          <span>高 {{ idx.high.toFixed(2) }}</span>
          <span>低 {{ idx.low.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- Market Breadth -->
    <div v-if="breadth.length" class="section">
      <h3 class="section-title">市场涨跌统计</h3>
      <p class="section-date">数据日期：{{ breadthDate }}</p>
      <div class="breadth-grid">
        <div v-for="b in filteredBreadth" :key="b.board" class="breadth-card">
          <div class="b-board">{{ b.board_label }}</div>
          <div class="b-bar-wrap">
            <div class="b-bar">
              <div class="b-up" :style="{ width: b.total ? (b.up_count / b.total * 100).toFixed(1) + '%' : '0%' }">
                <span v-if="b.up_count / b.total > 0.15">{{ b.up_count }}</span>
              </div>
              <div class="b-flat" :style="{ width: b.total ? (b.flat_count / b.total * 100).toFixed(1) + '%' : '0%' }">
                <span v-if="b.flat_count / b.total > 0.08">{{ b.flat_count }}</span>
              </div>
              <div class="b-down" :style="{ width: b.total ? (b.down_count / b.total * 100).toFixed(1) + '%' : '0%' }">
                <span v-if="b.down_count / b.total > 0.15">{{ b.down_count }}</span>
              </div>
            </div>
          </div>
          <div class="b-legend">
            <span class="leg-up">▲ {{ b.up_count }} 涨</span>
            <span class="leg-flat">— {{ b.flat_count }} 平</span>
            <span class="leg-down">▼ {{ b.down_count }} 跌</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Turnover -->
    <div v-if="turnover.length" class="section">
      <h3 class="section-title">市场总成交额</h3>
      <div class="turnover-summary" @click="showTurnoverChart = !showTurnoverChart" style="cursor:pointer">
        <div class="to-amount">{{ formatAmount(currentTurnover?.total_amount) }}</div>
        <div class="to-change" :class="{ up: turnoverChange >= 0, down: turnoverChange < 0 }">
          较前日 {{ turnoverChange >= 0 ? '+' : '' }}{{ formatAmount(Math.abs(turnoverChange)) }}
          <span style="font-size:11px;color:var(--color-text-muted);margin-left:4px">点击查看变化曲线</span>
        </div>
      </div>
      <div v-if="showTurnoverChart" ref="turnoverChartRef" style="width:100%;height:280px;margin-top:var(--space-3)"></div>
    </div>

    <!-- Sector Ranking -->
    <div v-if="sectors.length" class="section">
      <h3 class="section-title">行业板块</h3>
      <p class="section-date">数据日期：{{ sectorDate }}</p>
      <div class="sector-table">
        <div class="st-header">
          <span class="st-rank">#</span>
          <span class="st-name">板块</span>
          <span class="st-pct">涨跌幅</span>
          <span class="st-lead">领涨股</span>
        </div>
        <div v-for="s in sectors" :key="s.code" class="st-row" :class="{ up: s.change_pct >= 0, down: s.change_pct < 0 }">
          <span class="st-rank">{{ s.rank }}</span>
          <span class="st-name">{{ s.name }}</span>
          <span class="st-pct">{{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%</span>
          <span class="st-lead">{{ s.leading_stock || '--' }}</span>
        </div>
      </div>
    </div>

    <div v-if="!indices.length && !breadth.length" class="empty-state">
      <div class="icon">📈</div>
      <div class="title">暂无市场数据</div>
      <div class="desc">市场数据在交易日 15:05 自动更新，也可手动爬取</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import api from '../api'

const indices = ref([])
const breadth = ref([])
const sectors = ref([])
const breadthDate = ref('')
const sectorDate = ref('')
const turnover = ref([])
const showTurnoverChart = ref(false)
const turnoverChartRef = ref(null)
let turnoverChart = null

const currentTurnover = computed(() => turnover.value.length ? turnover.value[turnover.value.length - 1] : null)
const turnoverChange = computed(() => {
  if (turnover.value.length < 2) return 0
  return currentTurnover.value.total_amount - turnover.value[turnover.value.length - 2].total_amount
})

// Show ALL aggregate by default, individual boards as toggle
const filteredBreadth = computed(() => {
  const all = breadth.value.filter(b => b.board === 'ALL')
  return all.length ? all : breadth.value
})

function formatAmount(val) {
  if (!val) return '--'
  if (val >= 1e12) return (val / 1e12).toFixed(2) + ' 万亿'
  if (val >= 1e8) return (val / 1e8).toFixed(2) + ' 亿'
  return (val / 1e4).toFixed(0) + ' 万'
}

async function renderTurnoverChart() {
  if (!turnoverChartRef.value) return
  const data = turnover.value
  if (!data.length) return

  if (!turnoverChart) turnoverChart = echarts.init(turnoverChartRef.value)

  const amounts = data.map(d => +(d.total_amount / 1e8).toFixed(0))
  turnoverChart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#e5e7eb', textStyle: { color: '#1e2130' },
      formatter: p => `${p[0].axisValue}<br/>成交额: ${p[0].value} 亿` },
    grid: { left: '8%', right: '5%', top: 10, bottom: 10 },
    xAxis: { type: 'category', data: data.map(d => d.trade_date), axisLabel: { color: '#9ca3af', fontSize: 10 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f4f6' } }, axisLabel: { color: '#9ca3af', fontSize: 10, formatter: '{value}亿' } },
    series: [{
      type: 'bar', data: amounts,
      itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
      emphasis: { itemStyle: { color: '#2563eb' } },
    }],
  }, true)
}

watch(showTurnoverChart, async (v) => { if (v) { await nextTick(); renderTurnoverChart() } })

onMounted(async () => {
  try {
    const [ir, br, sr, tr] = await Promise.all([
      api.get('/market/indices'),
      api.get('/market/breadth'),
      api.get('/market/sectors', { params: { limit: 20 } }),
      api.get('/market/turnover', { params: { days: 60 } }),
    ])
    indices.value = ir.data.data
    breadth.value = br.data.data
    breadthDate.value = br.data.trade_date
    sectors.value = sr.data.data
    sectorDate.value = sr.data.trade_date
    turnover.value = tr.data.data
  } catch { /* ignore */ }
})
</script>

<style scoped>
/* ── Index Cards ── */
.index-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: var(--space-8);
}
@media (max-width: 1100px) { .index-grid { grid-template-columns: repeat(3, 1fr); } }

.index-card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  transition: all var(--transition-fast);
}
.index-card:hover { box-shadow: var(--shadow-md); }
.index-card.up { border-top: 3px solid var(--color-up); }
.index-card.down { border-top: 3px solid var(--color-down); }

.idx-name { font-size: var(--text-xs); color: var(--color-text-secondary); margin-bottom: 4px; font-weight: 500; }
.idx-close { font-family: var(--font-mono); font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; }
.idx-change { margin-top: 4px; font-size: var(--text-sm); }
.idx-chg-val { font-weight: 600; }
.up .idx-chg-val, .up .idx-chg-pct { color: var(--color-up); }
.down .idx-chg-val, .down .idx-chg-pct { color: var(--color-down); }
.idx-detail { margin-top: var(--space-3); display: flex; gap: var(--space-3); font-size: 11px; color: var(--color-text-muted); }

/* ── Breadth ── */
.section { margin-bottom: var(--space-8); }
.section-date { font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-3); }

.breadth-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-4); }
.breadth-card { background: var(--color-surface); border-radius: var(--radius-lg); padding: var(--space-5); border: 1px solid var(--color-border); }
.b-board { font-weight: 600; font-size: var(--text-base); margin-bottom: var(--space-3); }
.b-bar-wrap { margin-bottom: var(--space-2); }
.b-bar { display: flex; height: 28px; border-radius: 4px; overflow: hidden; }
.b-up { background: var(--color-up); display: flex; align-items: center; justify-content: center; font-size: 11px; color: #fff; font-weight: 600; min-width: 0; transition: width 0.5s ease; }
.b-flat { background: #d1d5db; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #6b7280; min-width: 0; }
.b-down { background: var(--color-down); display: flex; align-items: center; justify-content: center; font-size: 11px; color: #fff; font-weight: 600; min-width: 0; transition: width 0.5s ease; }
.b-legend { display: flex; gap: var(--space-4); font-size: var(--text-xs); }
.leg-up { color: var(--color-up); }
.leg-flat { color: var(--color-text-muted); }
.leg-down { color: var(--color-down); }

/* ── Sector Table ── */
.sector-table {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.st-header, .st-row {
  display: grid;
  grid-template-columns: 40px 1fr 100px 140px;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  gap: var(--space-3);
}
.st-header {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}
.st-row {
  font-size: var(--text-sm);
  border-bottom: 1px solid var(--color-divider);
  transition: background var(--transition-fast);
}
.st-row:hover { background: #fafbfc; }
.st-row:last-child { border-bottom: none; }
.st-rank { color: var(--color-text-muted); font-family: var(--font-mono); }
.st-name { font-weight: 500; }
.st-pct { font-family: var(--font-mono); font-weight: 600; font-variant-numeric: tabular-nums; }
.st-row.up .st-pct { color: var(--color-up); }
.st-row.down .st-pct { color: var(--color-down); }
.st-lead { color: var(--color-text-secondary); font-size: var(--text-xs); }

/* ── Turnover ── */
.turnover-summary {
  background: var(--color-surface); border-radius: var(--radius-lg);
  padding: var(--space-5); border: 1px solid var(--color-border);
  transition: all var(--transition-fast);
}
.turnover-summary:hover { border-color: var(--color-primary); box-shadow: var(--shadow-md); }
.to-amount { font-family: var(--font-mono); font-size: 28px; font-weight: 700; }
.to-change { font-size: var(--text-sm); margin-top: 4px; }
.to-change.up { color: var(--color-up); }
.to-change.down { color: var(--color-down); }
</style>

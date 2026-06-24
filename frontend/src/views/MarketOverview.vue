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
        <div v-for="b in breadth" :key="b.board" class="breadth-card">
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
import { ref, onMounted } from 'vue'
import api from '../api'

const indices = ref([])
const breadth = ref([])
const sectors = ref([])
const breadthDate = ref('')
const sectorDate = ref('')

onMounted(async () => {
  try {
    const [ir, br, sr] = await Promise.all([
      api.get('/market/indices'),
      api.get('/market/breadth'),
      api.get('/market/sectors', { params: { limit: 20 } }),
    ])
    indices.value = ir.data.data
    breadth.value = br.data.data
    breadthDate.value = br.data.trade_date
    sectors.value = sr.data.data
    sectorDate.value = sr.data.trade_date
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
</style>

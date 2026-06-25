<template>
  <div>
    <!-- Hero -->
    <div class="pf-hero">
      <div>
        <div class="back-link" @click="$router.push('/portfolios')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
          返回
        </div>
        <h1 class="pf-title">{{ portfolio.name }}</h1>
        <span class="pf-code-badge">{{ portfolio.code }}</span>
      </div>
      <div class="pf-hero-stats">
        <div>
          <div class="stat-label">最新净值</div>
          <div class="hero-value">¥{{ portfolio.latest_nav != null ? portfolio.latest_nav.toFixed(2) : '--' }}</div>
        </div>
        <div>
          <div class="stat-label">累计收益率</div>
          <div :class="['hero-value', (portfolio.latest_return_rate ?? 0) >= 0 ? 'up' : 'down']">
            {{ portfolio.latest_return_rate != null ? ((portfolio.latest_return_rate * 100).toFixed(2) + '%') : '--' }}
          </div>
        </div>
      </div>
    </div>

    <!-- Holdings -->
    <div class="section">
      <div class="section-header">
        <h3 class="section-title">持仓明细 · {{ portfolio.holdings?.length || 0 }} 只股票</h3>
        <button class="btn-primary-sm" @click="showAdd = true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          添加股票
        </button>
      </div>

      <div class="holdings-table">
        <div class="ht-header">
          <span class="col-c">代码</span>
          <span class="col-n">名称</span>
          <span class="col-s">持仓</span>
          <span class="col-p">成本价</span>
          <span class="col-a"></span>
        </div>
        <div v-for="h in portfolio.holdings" :key="h.id" class="ht-row">
          <span class="col-c"><span class="code-text">{{ h.stock_code }}</span></span>
          <span class="col-n">{{ h.stock_name }}</span>
          <span class="col-s">{{ h.shares }} 股</span>
          <span class="col-p">
            <span v-if="h.cost_price != null">¥{{ h.cost_price.toFixed(3) }}</span>
            <span v-else class="unset">未设定</span>
          </span>
          <span class="col-a">
            <button v-if="!h.is_cost_locked" class="btn-mini" @click="openSetCost(h)">设定成本</button>
            <span v-else class="locked-tag">已锁定</span>
            <button class="btn-mini danger" @click="handleRemove(h)">删除</button>
          </span>
        </div>
        <div v-if="!portfolio.holdings?.length" class="ht-empty">暂无持仓，点击上方按钮添加</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="section">
      <div class="chart-tabs">
        <button :class="['tab', { active: tab === 'curve' }]" @click="tab='curve';nextTick(renderCurve)">收益曲线</button>
        <button :class="['tab', { active: tab === 'heatmap' }]" @click="tab='heatmap';nextTick(renderHeatmap)">收益日历</button>
        <button :class="['tab', { active: tab === 'contrib' }]" @click="tab='contrib';nextTick(renderContribution)">贡献分析</button>
      </div>

      <div v-show="tab === 'curve'" class="chart-card">
        <div class="chart-range">
          <button v-for="r in ranges" :key="r.key" :class="['rng', { active: cr === r.key }]" @click="cr=r.key;renderCurve()">{{ r.label }}</button>
        </div>
        <div ref="curveRef" class="chart-box"></div>
      </div>

      <div v-show="tab === 'heatmap'" class="chart-card">
        <div class="chart-range">
          <select v-model="hy" @change="renderHeatmap" class="year-select">
            <option v-for="y in years" :key="y" :value="y">{{ y }} 年</option>
          </select>
        </div>
        <div ref="heatRef" class="chart-box" style="height:240px"></div>
      </div>

      <div v-show="tab === 'contrib'" class="chart-card">
        <div ref="contribRef" class="chart-box"></div>
      </div>
    </div>

    <!-- Add Dialog -->
    <teleport to="body">
      <div v-if="showAdd" class="overlay" @click.self="showAdd=false">
        <div class="dialog">
          <h3>添加股票持仓</h3>
          <div class="field">
            <label>股票代码</label>
            <div class="stock-search">
              <input
                v-model="searchQuery"
                type="text"
                placeholder="输入股票代码或名称搜索..."
                autocomplete="off"
                @focus="searchDropdown = searchResults.length > 0"
                @blur="onSearchBlur"
                @keydown.escape.prevent="closeSearchDropdown"
                @keydown.up.prevent="moveSearchUp"
                @keydown.down.prevent="moveSearchDown"
                @keydown.enter.prevent="handleSearchEnter"
              />
              <div v-if="searchDropdown && (searchLoading || searchResults.length > 0)" class="stock-dropdown">
                <div v-if="searchLoading" class="stock-dd-loading">搜索中...</div>
                <template v-else>
                  <div
                    v-for="(s, i) in searchResults" :key="s.code"
                    class="stock-dd-row"
                    :class="{ highlighted: highlightIdx === i }"
                    @mousedown.prevent="selectStock(s)"
                  >
                    <div class="stock-dd-info">
                      <span class="stock-dd-code">{{ s.code }}</span>
                      <span class="stock-dd-name">{{ s.name }}</span>
                      <span class="stock-dd-ex">{{ s.exchange === 'SH' ? '沪' : s.exchange === 'SZ' ? '深' : '京' }}</span>
                    </div>
                    <div class="stock-dd-price">
                      <span v-if="s.latest_close != null" class="stock-dd-close">{{ s.latest_close.toFixed(2) }}</span>
                      <span v-else class="stock-dd-close">--</span>
                      <span
                        v-if="s.change_pct != null"
                        class="stock-dd-chg"
                        :class="{ up: s.change_pct > 0, down: s.change_pct < 0 }"
                      >
                        {{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
                      </span>
                    </div>
                  </div>
                </template>
              </div>
              <div v-if="addForm.stock_code && selectedStockName" class="stock-selected">
                <span class="stock-sel-label">已选：</span>
                <span class="stock-sel-code">{{ addForm.stock_code }}</span>
                <span class="stock-sel-name">{{ selectedStockName }}</span>
              </div>
            </div>
          </div>
          <div class="field">
            <label>持仓股数</label>
            <input v-model.number="addForm.shares" type="number" min="1" step="100" />
          </div>
          <div class="field">
            <label>成本价 <small>（可选，不填则自动计算）</small></label>
            <input v-model.number="addForm.cost_price" type="number" min="0" step="0.01" placeholder="留空自动计算" />
          </div>
          <div class="dialog-actions">
            <button class="btn-cancel" @click="showAdd=false">取消</button>
            <button class="btn-primary-sm" @click="handleAdd">确定添加</button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Set Cost Dialog -->
    <teleport to="body">
      <div v-if="showCost" class="overlay" @click.self="showCost=false">
        <div class="dialog">
          <h3>设定成本价</h3>
          <p class="dialog-desc">成本价一旦设定，将不可修改。</p>
          <div class="field">
            <label>成本价</label>
            <input v-model.number="costForm.cost_price" type="number" min="0" step="0.01" />
          </div>
          <div class="dialog-actions">
            <button class="btn-cancel" @click="showCost=false">取消</button>
            <button class="btn-primary-sm" @click="handleSetCost">确认设定</button>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { portfolioApi, stockApi } from '../api'
import { ElMessageBox } from 'element-plus'

const route = useRoute()
const code = route.params.code

const portfolio = ref({ name: '', code: '', holdings: [], latest_nav: null, latest_return_rate: null })
const tab = ref('curve')
const cr = ref('6m')
const hy = ref(new Date().getFullYear())
const years = ref(Array.from({ length: 4 }, (_, i) => new Date().getFullYear() - i))

const ranges = [
  { key: '1m', label: '1月' }, { key: '3m', label: '3月' }, { key: '6m', label: '6月' },
  { key: '1y', label: '1年' }, { key: 'all', label: '全部' },
]

// Dialogs
const showAdd = ref(false)
const showCost = ref(false)
const addForm = ref({ stock_code: '', shares: 100, cost_price: null })
const costForm = ref({ holding_id: null, cost_price: 0 })

// Stock search in add dialog
const searchQuery = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const searchDropdown = ref(false)
const highlightIdx = ref(-1)
const selectedStockName = ref('')
let searchTimer = null

// Charts
const curveRef = ref(null), heatRef = ref(null), contribRef = ref(null)
let cc = null, hc = null, oc = null

async function refresh() {
  const { data } = await portfolioApi.detail(code)
  portfolio.value = data
}

// Reset search when dialog opens/closes
watch(showAdd, (v) => {
  if (!v) {
    searchQuery.value = ''
    searchResults.value = []
    searchDropdown.value = false
    highlightIdx.value = -1
    selectedStockName.value = ''
  }
})

// ── Stock search ──
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  highlightIdx.value = -1
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    searchDropdown.value = false
    return
  }
  searchTimer = setTimeout(async () => {
    searchLoading.value = true
    searchDropdown.value = true
    try {
      const { data } = await stockApi.search(searchQuery.value.trim(), 8)
      searchResults.value = data.items
    } finally {
      searchLoading.value = false
    }
  }, 200)
})

function selectStock(s) {
  addForm.value.stock_code = s.code
  selectedStockName.value = s.name
  closeSearchDropdown()
}

function closeSearchDropdown() {
  clearTimeout(searchTimer)
  searchDropdown.value = false
  searchQuery.value = ''
  searchResults.value = []
  highlightIdx.value = -1
}

function onSearchBlur() {
  setTimeout(() => { searchDropdown.value = false }, 150)
}

function moveSearchUp() {
  if (!searchDropdown.value || searchResults.value.length === 0) return
  highlightIdx.value = highlightIdx.value <= 0 ? searchResults.value.length - 1 : highlightIdx.value - 1
}

function moveSearchDown() {
  if (!searchDropdown.value || searchResults.value.length === 0) return
  highlightIdx.value = highlightIdx.value >= searchResults.value.length - 1 ? 0 : highlightIdx.value + 1
}

function handleSearchEnter() {
  if (!searchDropdown.value || searchResults.value.length === 0) return
  if (highlightIdx.value >= 0 && highlightIdx.value < searchResults.value.length) {
    selectStock(searchResults.value[highlightIdx.value])
  }
}

// ── Holdings ──
async function handleAdd() {
  try {
    await portfolioApi.addHolding(code, {
      stock_code: addForm.value.stock_code,
      shares: addForm.value.shares,
      cost_price: addForm.value.cost_price || null,
    })
    showAdd.value = false
    addForm.value = { stock_code: '', shares: 100, cost_price: null }
    selectedStockName.value = ''
    searchQuery.value = ''
    refresh()
  } catch { /* handled */ }
}

async function handleRemove(h) {
  try { await ElMessageBox.confirm(`确定删除 ${h.stock_name}？`); await portfolioApi.removeHolding(code, h.id); refresh() }
  catch { /* cancelled */ }
}

function openSetCost(h) { costForm.value = { holding_id: h.id, cost_price: 0 }; showCost.value = true }
async function handleSetCost() {
  try { await portfolioApi.setCost(code, costForm.value.holding_id, { cost_price: costForm.value.cost_price }); showCost.value = false; refresh() }
  catch { /* handled */ }
}

// ── Charts ──
function getDR() {
  const today = new Date()
  const e = today.toISOString().slice(0, 10)
  const m = { '1m': 30, '3m': 90, '6m': 180, '1y': 365, all: 3650 }
  return { start: new Date(today.getTime() - m[cr.value] * 86400000).toISOString().slice(0, 10), end: e }
}

async function renderCurve() {
  const { start, end } = getDR()
  const { data: res } = await portfolioApi.nav(code, start, end)
  if (!cc && curveRef.value) cc = echarts.init(curveRef.value)
  if (!cc) return
  cc.setOption({
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#e5e7eb', textStyle: { color: '#1e2130', fontSize: 12 } },
    grid: { left: '8%', right: '5%', top: 10, bottom: 10 },
    xAxis: { type: 'category', data: res.data.map(d => d.date), axisLine: { lineStyle: { color: '#e5e7eb' } }, axisLabel: { color: '#9ca3af', fontSize: 10 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f4f6' } }, axisLabel: { color: '#9ca3af', fontSize: 10, formatter: '{value}%' } },
    series: [{
      type: 'line', data: res.data.map(d => d.cum_return_rate != null ? +(d.cum_return_rate * 100).toFixed(2) : null),
      smooth: true, symbol: 'none',
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(59,130,246,0.15)' }, { offset: 1, color: 'rgba(59,130,246,0)' }]) },
      lineStyle: { color: '#3b82f6', width: 2 },
      markLine: { data: [{ yAxis: 0 }], lineStyle: { color: '#d1d5db', type: 'dashed' }, symbol: 'none' },
    }],
  }, true)
}

async function renderHeatmap() {
  const { data: res } = await portfolioApi.dailyReturns(code, hy.value)
  const data = res.data.map(d => [d.date, d.return_rate != null ? +(d.return_rate * 100).toFixed(2) : 0])
  if (!hc && heatRef.value) hc = echarts.init(heatRef.value)
  if (!hc) return
  hc.setOption({
    tooltip: { backgroundColor: '#fff', borderColor: '#e5e7eb', textStyle: { color: '#1e2130' }, formatter: p => `${p.data[0]}<br/>收益率: ${p.data[1]}%` },
    visualMap: { min: -10, max: 10, inRange: { color: ['#1aad56', '#f0faf5', '#fef2f0', '#e15241'] }, show: false },
    calendar: { range: String(hy.value), cellSize: ['auto', 18], dayLabel: { nameMap: 'ZH', color: '#9ca3af' }, monthLabel: { nameMap: 'ZH', color: '#9ca3af' }, itemStyle: { borderColor: '#fff', borderWidth: 2 } },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', data }],
  }, true)
}

async function renderContribution() {
  const { data: res } = await portfolioApi.contributions(code)
  if (!oc && contribRef.value) oc = echarts.init(contribRef.value)
  if (!oc) return
  const vals = res.data.map(d => d.return_amount ?? 0)
  oc.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#fff', borderColor: '#e5e7eb', textStyle: { color: '#1e2130' } },
    grid: { left: '5%', right: '10%', top: 10, bottom: 10 },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f4f6' } }, axisLabel: { color: '#9ca3af', formatter: '¥{value}' } },
    yAxis: { type: 'category', data: res.data.map(d => d.stock_name), axisLine: { lineStyle: { color: '#e5e7eb' } }, axisLabel: { color: '#1e2130', fontWeight: 500 } },
    series: [{
      type: 'bar', data: vals.map((v, i) => ({ value: v, itemStyle: { color: v >= 0 ? '#e15241' : '#1aad56', borderRadius: [0, 4, 4, 0] } })),
      label: { show: true, position: 'right', color: '#6b7280', formatter: p => '¥' + Math.abs(p.value).toFixed(0) },
    }],
  }, true)
}

onMounted(async () => { await refresh(); await nextTick(); renderCurve() })
const hr = () => { cc?.resize(); hc?.resize(); oc?.resize() }
window.addEventListener('resize', hr)
onUnmounted(() => { window.removeEventListener('resize', hr); cc?.dispose(); hc?.dispose(); oc?.dispose() })
</script>

<style scoped>
/* ── Hero ── */
.pf-hero {
  display: flex; justify-content: space-between; align-items: flex-end;
  background: var(--color-surface); border-radius: var(--radius-lg);
  padding: var(--space-6) var(--space-8); margin-bottom: var(--space-6);
  box-shadow: var(--shadow-sm);
}
.back-link { display: inline-flex; align-items: center; gap: 4px; font-size: var(--text-sm); color: var(--color-text-secondary); cursor: pointer; margin-bottom: var(--space-2); }
.back-link:hover { color: var(--color-primary); }
.pf-title { font-size: var(--text-2xl); font-weight: 700; letter-spacing: -0.02em; }
.pf-code-badge { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--color-text-muted); background: var(--color-bg); padding: 2px 8px; border-radius: 4px; }
.pf-hero-stats { display: flex; gap: var(--space-8); text-align: right; }
.hero-value { font-family: var(--font-mono); font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; }
.hero-value.up { color: var(--color-up); }
.hero-value.down { color: var(--color-down); }

/* ── Section ── */
.section { margin-bottom: var(--space-6); }

/* ── Holdings table ── */
.holdings-table {
  background: var(--color-surface); border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm); overflow: hidden;
}
.ht-header, .ht-row {
  display: grid;
  grid-template-columns: 100px 1fr 100px 120px 200px;
  align-items: center; padding: var(--space-3) var(--space-5); gap: var(--space-3);
}
.ht-header { font-size: var(--text-xs); color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 0.05em; background: var(--color-bg); border-bottom: 1px solid var(--color-border); }
.ht-row { border-bottom: 1px solid var(--color-divider); font-size: var(--text-base); }
.ht-row:last-child { border-bottom: none; }
.ht-empty { text-align: center; padding: var(--space-8); color: var(--color-text-muted); font-size: var(--text-sm); }

.code-text { font-family: var(--font-mono); font-weight: 600; }
.unset { color: var(--color-text-muted); font-style: italic; }

.btn-primary-sm {
  display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 var(--space-4);
  background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff; border: none;
  border-radius: var(--radius-sm); font-size: var(--text-sm); font-weight: 600;
  cursor: pointer; font-family: inherit; transition: all var(--transition-fast);
}
.btn-primary-sm:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(37,99,235,0.35); }

.btn-mini { height: 26px; padding: 0 var(--space-2); border-radius: 4px; font-size: var(--text-xs); font-weight: 500; cursor: pointer; border: none; font-family: inherit; background: var(--color-bg); color: var(--color-text-secondary); transition: all var(--transition-fast); }
.btn-mini:hover { background: #e5e7eb; color: var(--color-text-primary); }
.btn-mini.danger:hover { background: #fef2f2; color: var(--color-danger); }
.locked-tag { font-size: var(--text-xs); color: var(--color-text-muted); background: var(--color-bg); padding: 2px 8px; border-radius: 4px; }

/* ── Chart tabs ── */
.chart-tabs { display: flex; gap: 0; background: var(--color-surface); border-radius: var(--radius-lg) var(--radius-lg) 0 0; box-shadow: var(--shadow-sm); }
.tab { padding: var(--space-3) var(--space-5); border: none; background: transparent; font-size: var(--text-sm); font-weight: 500; color: var(--color-text-secondary); cursor: pointer; font-family: inherit; border-bottom: 2px solid transparent; transition: all var(--transition-fast); }
.tab.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }
.tab:hover:not(.active) { color: var(--color-text-primary); }
.chart-card { background: var(--color-surface); border-radius: 0 0 var(--radius-lg) var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-sm); }
.chart-box { width: 100%; height: 380px; }
.chart-range { display: flex; gap: 4px; margin-bottom: var(--space-3); }
.rng { padding: 4px 12px; border: none; background: transparent; border-radius: 4px; font-size: var(--text-xs); color: var(--color-text-secondary); cursor: pointer; font-family: inherit; }
.rng.active { background: var(--color-primary-light); color: var(--color-primary); font-weight: 600; }
.year-select { height: 30px; padding: 0 var(--space-2); border: 1px solid var(--color-border); border-radius: 4px; font-size: var(--text-sm); font-family: inherit; color: var(--color-text-primary); background: var(--color-surface); }

/* ── Dialogs ── */
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 200; }
.dialog { width: 400px; background: var(--color-surface); border-radius: var(--radius-xl); padding: var(--space-6); box-shadow: var(--shadow-xl); }
.dialog h3 { font-size: var(--text-lg); font-weight: 700; margin-bottom: var(--space-1); }
.dialog-desc { font-size: var(--text-sm); color: var(--color-text-secondary); margin-bottom: var(--space-4); }
.field { margin-bottom: var(--space-4); }
.field label { display: block; font-size: var(--text-sm); font-weight: 500; margin-bottom: 6px; }
.field label small { color: var(--color-text-muted); font-weight: 400; }
.field input { width: 100%; height: 40px; padding: 0 var(--space-3); background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--text-base); font-family: inherit; outline: none; transition: border-color var(--transition-fast); }
.field input:focus { border-color: var(--color-primary); }
.dialog-actions { display: flex; gap: var(--space-3); justify-content: flex-end; margin-top: var(--space-5); }
.btn-cancel { height: 36px; padding: 0 var(--space-4); background: transparent; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--text-sm); font-weight: 500; cursor: pointer; font-family: inherit; color: var(--color-text-secondary); }
.btn-cancel:hover { background: var(--color-bg); }

/* ── Stock search dropdown ── */
.stock-search { position: relative; }
.stock-search input {
  width: 100%; height: 40px; padding: 0 var(--space-3);
  background: var(--color-bg); border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); font-size: var(--text-base);
  font-family: inherit; outline: none;
  transition: border-color var(--transition-fast);
}
.stock-search input:focus { border-color: var(--color-primary); }

.stock-dropdown {
  position: absolute; top: 44px; left: 0; right: 0;
  background: var(--color-surface); border-radius: 8px;
  box-shadow: var(--shadow-xl); border: 1px solid var(--color-border);
  max-height: 280px; overflow-y: auto; z-index: 210;
}
.stock-dd-loading {
  padding: var(--space-4); text-align: center;
  font-size: var(--text-sm); color: var(--color-text-muted);
}

.stock-dd-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-2) var(--space-3); cursor: pointer;
  border-bottom: 1px solid var(--color-divider);
  transition: background var(--transition-fast);
}
.stock-dd-row:last-child { border-bottom: none; }
.stock-dd-row:hover { background: var(--color-bg); }
.stock-dd-row.highlighted { background: var(--color-primary-light); }

.stock-dd-info { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.stock-dd-code { font-family: var(--font-mono); font-weight: 600; font-size: 13px; }
.stock-dd-name { font-size: 13px; color: var(--color-text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stock-dd-ex {
  font-size: 10px; padding: 1px 5px; border-radius: 3px; flex-shrink: 0;
  background: var(--color-bg); color: var(--color-text-muted);
}

.stock-dd-price { display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0; margin-left: var(--space-3); }
.stock-dd-close { font-family: var(--font-mono); font-size: 13px; font-weight: 600; }
.stock-dd-chg { font-family: var(--font-mono); font-size: 11px; font-weight: 500; padding: 1px 6px; border-radius: 4px; min-width: 56px; text-align: center; }
.stock-dd-chg.up { color: #fff; background: var(--color-up); }
.stock-dd-chg.down { color: #fff; background: var(--color-down); }

/* ── Selected stock confirmation ── */
.stock-selected {
  display: flex; align-items: center; gap: 6px;
  margin-top: var(--space-2); padding: var(--space-2) var(--space-3);
  background: var(--color-primary-light); border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}
.stock-sel-label { color: var(--color-primary); font-weight: 500; }
.stock-sel-code { font-family: var(--font-mono); font-weight: 600; }
.stock-sel-name { color: var(--color-text-secondary); }
</style>

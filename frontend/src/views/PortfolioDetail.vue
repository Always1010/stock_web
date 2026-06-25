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
          <div class="stat-label">累计收益</div>
          <div :class="['hero-value', (heroCumReturn ?? 0) >= 0 ? 'up' : 'down']">
            {{ heroCumReturn != null ? fmtMoney(heroCumReturn) : '--' }}
          </div>
        </div>
        <div>
          <div class="stat-label">累计收益率</div>
          <div :class="['hero-value', (heroCumRate ?? 0) >= 0 ? 'up' : 'down']">
            {{ heroCumRate != null ? fmtRate(heroCumRate) : '--' }}
          </div>
        </div>
      </div>
    </div>

    <!-- Actions Bar -->
    <div class="pf-actions">
      <div class="action-group">
        <label class="action-label">收益起始日</label>
        <div class="date-picker-wrap">
          <template v-if="!editingStartDate">
            <span :class="['date-display', { muted: !returnStartDateStr }]">{{ returnStartDateStr || '未设定' }}</span>
            <button class="action-btn-sm" @click="startEditStartDate" title="编辑起始日">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
          </template>
          <template v-else>
            <input
              type="date"
              v-model="editStartDateVal"
              class="date-input"
            />
            <button class="action-btn-sm confirm" @click="confirmStartDate" title="确认">✓</button>
            <button class="action-btn-sm" @click="cancelStartDate" title="取消">✕</button>
          </template>
        </div>
      </div>

      <div class="action-divider"></div>

      <div class="action-group">
        <label class="action-label">数据更新</label>
        <div class="btn-row">
          <button class="action-btn" :disabled="refreshingData" @click="handleFullDataRefresh">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 :class="{ spinning: refreshingData }">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
            {{ refreshingData ? '更新中...' : '全量更新' }}
          </button>
          <button class="action-btn" :disabled="refreshingData" @click="handleIncrDataRefresh">增量更新</button>
        </div>
      </div>

      <div class="action-divider"></div>

      <div class="action-group">
        <label class="action-label">收益计算</label>
        <div class="btn-row">
          <button class="action-btn" :disabled="refreshingNav" @click="handleFullNavRecalc">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 :class="{ spinning: refreshingNav }">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
            {{ refreshingNav ? '计算中...' : '全量更新' }}
          </button>
          <button class="action-btn" :disabled="refreshingNav" @click="handleIncrNavRecalc">增量更新</button>
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
          <span class="col-n">名称</span>
          <span class="col-c">代码</span>
          <span class="col-s">持仓</span>
          <span class="col-p">成本价</span>
          <span class="col-cp">现价</span>
          <span class="col-dr">当日收益率</span>
          <span class="col-ra">累计收益</span>
          <span class="col-rr">累计收益率</span>
          <span class="col-a"></span>
        </div>
        <div v-for="h in enrichedHoldings" :key="h.id" class="ht-row" @click="$router.push(`/stocks/${h.stock_code}/kline`)">
          <span class="col-n">{{ h.stock_name }}</span>
          <span class="col-c"><span class="code-text">{{ h.stock_code }}</span></span>
          <span class="col-s">{{ h.shares }} 股</span>
          <span class="col-p">
            <span v-if="h.cost_price != null">¥{{ h.cost_price.toFixed(3) }}</span>
            <span v-else class="unset">未设定</span>
          </span>
          <span class="col-cp">
            <span v-if="h.current_price != null">¥{{ h.current_price.toFixed(2) }}</span>
            <span v-else class="unset">--</span>
          </span>
          <span class="col-dr">
            <span v-if="h._dailyReturnRate != null" :class="rateClass(h._dailyReturnRate)">{{ fmtRate(h._dailyReturnRate) }}</span>
            <span v-else class="unset">--</span>
          </span>
          <span class="col-ra">
            <span v-if="h._returnAmount != null" :class="moneyClass(h._returnAmount)">{{ fmtMoney(h._returnAmount) }}</span>
            <span v-else class="unset">--</span>
          </span>
          <span class="col-rr">
            <span v-if="h._returnRate != null" :class="rateClass(h._returnRate)">{{ fmtRate(h._returnRate) }}</span>
            <span v-else class="unset">--</span>
          </span>
          <span class="col-a" @click.stop>
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
        <button :class="['tab', { active: tab === 'calendar' }]" @click="tab='calendar';nextTick(renderCalendar)">收益日历</button>
        <button :class="['tab', { active: tab === 'contrib' }]" @click="tab='contrib';nextTick(renderContribution)">贡献分析</button>
      </div>

      <div v-show="tab === 'curve'" class="chart-card">
        <div class="chart-range">
          <button v-for="r in ranges" :key="r.key" :class="['rng', { active: cr === r.key }]" @click="cr=r.key;renderCurve()">{{ r.label }}</button>
        </div>
        <div ref="curveRef" class="chart-box"></div>
      </div>

      <div v-show="tab === 'calendar'" class="chart-card">
        <!-- Year Selector -->
        <div class="cal-year-nav">
          <button class="cal-nav-btn" @click="calYear--;renderCalendar()">&lt;</button>
          <span class="cal-year-label">{{ calYear }} 年</span>
          <button class="cal-nav-btn" @click="calYear++;renderCalendar()">&gt;</button>
        </div>

        <!-- Yearly Month Calendar -->
        <div class="cal-section-label">年度月历</div>
        <div class="cal-month-grid">
          <div
            v-for="m in 12" :key="'m'+m"
            :class="['cal-month-cell', monthCellBgClass(m), {
              active: selectedMonth === m,
              disabled: !isMonthEnabled(m),
            }]"
            @click="selectMonth(m)"
          >
            <div class="cal-cell-month">{{ m }}月</div>
            <template v-if="monthMap[m] && (monthMap[m].return_amount != null || monthMap[m].return_rate != null)">
              <div :class="['cal-cell-amount', moneyClass(monthMap[m].return_amount ?? 0)]">
                {{ monthMap[m].return_amount != null ? fmtMoney(monthMap[m].return_amount) : '--' }}
              </div>
              <div :class="['cal-cell-rate', rateClass(monthMap[m].return_rate ?? 0)]">
                {{ monthMap[m].return_rate != null ? fmtRate(monthMap[m].return_rate) : '--' }}
              </div>
            </template>
            <div v-else class="cal-cell-no-data">无数据</div>
          </div>
        </div>

        <!-- Monthly Day Calendar -->
        <div class="cal-section-label">月度日历 — {{ calYear }}年{{ calMonth }}月</div>
        <div class="cal-day-header">
          <span v-for="d in dayHeaders" :key="d" class="cal-dh-cell">{{ d }}</span>
        </div>
        <div class="cal-day-grid">
          <div
            v-for="(cell, idx) in dayCells" :key="'d'+idx"
            :class="['cal-day-cell', dayCellBgClass(cell.dateStr), {
              active: cell.day != null && selectedDay === cell.day,
              disabled: cell.day != null && !isDayEnabled(cell.dateStr),
              empty: cell.day == null,
            }]"
            @click="cell.day != null && isDayEnabled(cell.dateStr) && selectDay(cell.day, cell.dateStr)"
          >
            <template v-if="cell.day != null">
              <div class="cal-cell-day">{{ cell.day }}</div>
              <template v-if="dayDataMap[cell.dateStr] && (dayDataMap[cell.dateStr].return_amount != null || dayDataMap[cell.dateStr].return_rate != null)">
                <div v-if="dayDataMap[cell.dateStr].return_amount != null" :class="['cal-cell-amount', moneyClass(dayDataMap[cell.dateStr].return_amount)]">
                  {{ fmtMoney(dayDataMap[cell.dateStr].return_amount) }}
                </div>
                <div v-if="dayDataMap[cell.dateStr].return_rate != null" :class="['cal-cell-rate', rateClass(dayDataMap[cell.dateStr].return_rate)]">
                  {{ fmtRate(dayDataMap[cell.dateStr].return_rate) }}
                </div>
              </template>
            </template>
          </div>
        </div>

        <!-- Contribution Analysis (linked to selection) -->
        <div class="cal-section-label">贡献分析 — {{ contribTitle }}</div>
        <div ref="calContribRef" class="chart-box" style="height:300px"></div>
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
import { ref, watch, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { portfolioApi, stockApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  calcReturnAmount, calcReturnRate, calcDailyReturnRate,
  calcCumReturn, calcNavSeries, calcDailyReturns, calcMonthlyReturns, calcContributions,
  fmtMoney, fmtRate, moneyClass, rateClass,
} from '../utils/portfolioCalc'

const route = useRoute()
const code = route.params.code

const portfolio = ref({ name: '', code: '', holdings: [], latest_nav: null, latest_return_rate: null })
const tab = ref('curve')
const cr = ref('6m')

// Calendar state
const calYear = ref(new Date().getFullYear())
const calMonth = ref(new Date().getMonth() + 1)
const selectedMonth = ref(null)   // null = show full year contributions
const selectedDay = ref(null)
const selectedPeriod = ref({ type: 'year', start: '', end: '' })
const monthMap = ref({})
const dayDataMap = ref({})
const rawHoldings = ref([])  // 原始持仓K线数据，供前端计算 NAV/贡献
const dayHeaders = ['日', '一', '二', '三', '四', '五', '六']

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

// Actions bar
const returnStartDateStr = ref('')
const editingStartDate = ref(false)
const editStartDateVal = ref('')
const refreshingData = ref(false)
const refreshingNav = ref(false)

// Charts
const curveRef = ref(null), contribRef = ref(null), calContribRef = ref(null)
let cc = null, oc = null, calCc = null

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

// Sync return_start_date from portfolio data
watch(() => portfolio.value.return_start_date, (val) => {
  returnStartDateStr.value = val || ''
})

// ── Actions bar handlers ──

function startEditStartDate() {
  editStartDateVal.value = returnStartDateStr.value || ''
  editingStartDate.value = true
}

function cancelStartDate() {
  editingStartDate.value = false
  editStartDateVal.value = ''
}

async function confirmStartDate() {
  const val = editStartDateVal.value || null
  try {
    await portfolioApi.setReturnStartDate(code, { return_start_date: val })
    returnStartDateStr.value = val || ''
    ElMessage.success(val ? `收益起始日已设为 ${val}` : '收益起始日已清除')
    editingStartDate.value = false
    await refresh()
    rawHoldings.value = []  // 清除 K 线缓存，下次日历会重新加载
    await nextTick()
    if (tab.value === 'calendar') renderCalendar()
  } catch { /* handled */ }
}

async function handleFullDataRefresh() {
  refreshingData.value = true
  try {
    const { data } = await portfolioApi.refreshData(code)
    ElMessage.success(data.message || '全量数据更新完成')
    await refresh()
  } catch { /* handled */ }
  finally { refreshingData.value = false }
}

async function handleIncrDataRefresh() {
  refreshingData.value = true
  try {
    const { data } = await portfolioApi.refreshDataIncr(code)
    ElMessage.success(data.message || '增量数据更新完成')
    await refresh()
  } catch { /* handled */ }
  finally { refreshingData.value = false }
}

async function handleFullNavRecalc() {
  refreshingNav.value = true
  try {
    const { data } = await portfolioApi.recalcNav(code)
    ElMessage.success(data.message || '全量收益计算完成')
    await refresh()
    await nextTick()
    if (tab.value === 'curve') renderCurve()
    else if (tab.value === 'calendar') renderCalendar()
    else if (tab.value === 'contrib') renderContribution()
  } catch { /* handled */ }
  finally { refreshingNav.value = false }
}

async function handleIncrNavRecalc() {
  refreshingNav.value = true
  try {
    const { data } = await portfolioApi.recalcNavIncr(code)
    ElMessage.success(data.message || '增量收益计算完成')
    await refresh()
    await nextTick()
    if (tab.value === 'curve') renderCurve()
    else if (tab.value === 'calendar') renderCalendar()
    else if (tab.value === 'contrib') renderContribution()
  } catch { /* handled */ }
  finally { refreshingNav.value = false }
}

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

// ── 前端计算：用原始数据自行算出持仓衍生指标，与后端返回值等效 ──
const enrichedHoldings = computed(() => {
  return portfolio.value.holdings.map(h => ({
    ...h,
    _returnAmount: calcReturnAmount(h.current_price, h.cost_price, h.shares),
    _returnRate: calcReturnRate(h.current_price, h.cost_price),
    _dailyReturnRate: calcDailyReturnRate(h.current_price, h.prev_close),
  }))
})

// 前端计算 Hero 累计收益/收益率（无需依赖后端便捷计算字段）
const heroCumReturn = computed(() => {
  const p = portfolio.value
  return calcCumReturn(p.latest_nav, p.latest_total_cost)
})
const heroCumRate = computed(() => {
  const p = portfolio.value
  return calcReturnRate(p.latest_nav, p.latest_total_cost)
})

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
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e5e7eb',
      textStyle: { color: '#1e2130', fontSize: 12 },
      formatter: (params) => {
        const p = params[0]
        if (p.value == null) return `${p.axisValue}<br/>收益率: --`
        return `${p.axisValue}<br/>收益率: <b>${p.value.toFixed(2)}%</b>`
      },
    },
    grid: { left: '8%', right: '5%', top: 10, bottom: 10 },
    xAxis: { type: 'category', data: res.data.map(d => d.date), axisLine: { lineStyle: { color: '#e5e7eb' } }, axisLabel: { color: '#9ca3af', fontSize: 10 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f4f6' } }, axisLabel: { color: '#9ca3af', fontSize: 10, formatter: '{value}%' } },
    series: [{
      type: 'line', data: res.data.map(d => d.cum_return_rate != null ? +(d.cum_return_rate * 100).toFixed(2) : null),
      smooth: false, symbol: 'none',
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(59,130,246,0.15)' }, { offset: 1, color: 'rgba(59,130,246,0)' }]) },
      lineStyle: { color: '#3b82f6', width: 2 },
      markLine: { data: [{ yAxis: 0 }], lineStyle: { color: '#d1d5db', type: 'dashed' }, symbol: 'none' },
    }],
  }, true)
}

// ── Calendar ──

function selectMonth(m) {
  if (!isMonthEnabled(m)) return
  if (selectedMonth.value === m) {
    // Deselect: show full year contributions
    selectedMonth.value = null
    selectedDay.value = null
    const startStr = `${calYear.value}-01-01`
    const endStr = `${calYear.value}-12-31`
    selectedPeriod.value = { type: 'year', start: startStr, end: endStr }
    fetchContribForPeriod(startStr, endStr)
    return
  }
  selectedMonth.value = m
  calMonth.value = m
  selectedDay.value = null
  const startStr = `${calYear.value}-${String(m).padStart(2, '0')}-01`
  const lastDay = new Date(calYear.value, m, 0).getDate()
  const endStr = `${calYear.value}-${String(m).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  selectedPeriod.value = { type: 'month', start: startStr, end: endStr }
  fetchContribForPeriod(startStr, endStr)
}

function selectDay(day, dateStr) {
  if (!isDayEnabled(dateStr)) return
  selectedDay.value = day
  selectedPeriod.value = { type: 'day', start: dateStr, end: dateStr }
  fetchContribForPeriod(dateStr, dateStr)
}

const dayCells = computed(() => {
  const year = calYear.value
  const month = calMonth.value
  const firstDay = new Date(year, month - 1, 1)
  const lastDate = new Date(year, month, 0).getDate()
  // Sunday-first: getDay() returns 0=Sun -> 0 padding cells
  const startDow = firstDay.getDay()

  const cells = []
  for (let i = 0; i < startDow; i++) {
    cells.push({ day: null, dateStr: '' })
  }
  for (let d = 1; d <= lastDate; d++) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ day: d, dateStr })
  }
  return cells
})

const contribTitle = computed(() => {
  if (selectedPeriod.value.type === 'day') return selectedPeriod.value.start
  if (selectedPeriod.value.type === 'month') return `${calYear.value}年${selectedMonth.value}月`
  return `${calYear.value}年全年`
})

function monthCellBgClass(m) {
  const d = monthMap.value[m]
  if (!d || d.return_amount == null) return ''
  return d.return_amount > 0 ? 'bg-up' : d.return_amount < 0 ? 'bg-down' : ''
}
function dayCellBgClass(dateStr) {
  const d = dayDataMap.value[dateStr]
  if (!d || d.return_amount == null) return ''
  return d.return_amount > 0 ? 'bg-up' : d.return_amount < 0 ? 'bg-down' : ''
}

/**
 * 首次加载：一次性获取从 return_start_date 到今天的全部原始 K 线数据。
 * 后续切换年份/月份不再访问后端，全部从 rawHoldings 缓存中前端计算。
 */
async function loadAllKlineData() {
  try {
    const rsd = portfolio.value.return_start_date || '2020-01-01'
    const today = new Date().toISOString().slice(0, 10)
    const { data: res } = await portfolioApi.holdingsKline(code, rsd, today)
    rawHoldings.value = res.holdings
  } catch {
    rawHoldings.value = []
  }
}

/** 从缓存的 rawHoldings 计算当前年份的日历数据（纯前端，不访问后端） */
function computeCalendarForYear() {
  if (rawHoldings.value.length === 0) {
    monthMap.value = {}
    dayDataMap.value = {}
    return
  }
  const navSeries = calcNavSeries(rawHoldings.value)

  const monthly = calcMonthlyReturns(navSeries, calYear.value)
  const mmap = {}
  monthly.forEach(item => { mmap[item.month] = item })
  monthMap.value = mmap

  const dailyMap = calcDailyReturns(navSeries)
  dayDataMap.value = Object.fromEntries(dailyMap)
}

/**
 * 前端计算贡献分析（不再调用 /contributions 端点）。
 * 使用 loadCalendarData 中缓存的 rawHoldings 原始 K 线数据。
 */
function fetchContribForPeriod(start, end) {
  try {
    if (rawHoldings.value.length === 0) return
    const items = calcContributions(rawHoldings.value, start, end)
    if (!calCc && calContribRef.value) calCc = echarts.init(calContribRef.value)
    if (!calCc) return
    const vals = items.map(d => d.return_amount ?? 0)
    calCc.setOption({
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        backgroundColor: '#fff', borderColor: '#e5e7eb',
        textStyle: { color: '#1e2130' },
        formatter: (params) => {
          const p = params[0]
          const item = items[p.dataIndex]
          if (!item) return p.name
          const amount = item.return_amount != null ? '¥' + item.return_amount.toFixed(2) : '--'
          const rate = item.return_rate != null ? ((item.return_rate * 100).toFixed(2) + '%') : '--'
          return `<b>${item.stock_name}</b> (${item.stock_code})<br/>收益: ${amount}<br/>收益率: ${rate}`
        },
      },
      grid: { left: '5%', right: '10%', top: 10, bottom: 10 },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f4f6' } }, axisLabel: { color: '#9ca3af', formatter: '¥{value}' } },
      yAxis: { type: 'category', data: items.map(d => d.stock_name), axisLine: { lineStyle: { color: '#e5e7eb' } }, axisLabel: { color: '#1e2130', fontWeight: 500 } },
      series: [{
        type: 'bar', data: vals.map((v, i) => ({ value: v, itemStyle: { color: v >= 0 ? '#e15241' : '#1aad56', borderRadius: [0, 4, 4, 0] } })),
        label: { show: true, position: 'right', color: '#6b7280', formatter: p => '¥' + Math.abs(p.value).toFixed(0) },
      }],
    }, true)
  } catch { /* handled */ }
}

async function renderCalendar() {
  // 首次加载全量 K 线数据（仅一次），后续切换年份纯前端计算
  if (rawHoldings.value.length === 0) await loadAllKlineData()
  computeCalendarForYear()
  if (!isMonthEnabled(calMonth.value)) {
    for (let m = 1; m <= 12; m++) {
      if (isMonthEnabled(m)) { calMonth.value = m; break }
    }
  }
  // Default: full year contribution (no month selected)
  selectedMonth.value = null
  selectedDay.value = null
  const yearStart = `${calYear.value}-01-01`
  const yearEnd = `${calYear.value}-12-31`
  selectedPeriod.value = { type: 'year', start: yearStart, end: yearEnd }
  await fetchContribForPeriod(yearStart, yearEnd)
}

function getReturnStartDate() {
  return portfolio.value.return_start_date || null
}

function isMonthEnabled(m) {
  const rsd = getReturnStartDate()
  if (!rsd) return true
  const monthEnd = new Date(calYear.value, m, 0)
  const rsdDate = new Date(rsd + 'T00:00:00')
  return monthEnd >= rsdDate
}

function isDayEnabled(dateStr) {
  const rsd = getReturnStartDate()
  if (!rsd) return true
  return dateStr >= rsd
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
const hr = () => { cc?.resize(); oc?.resize(); calCc?.resize() }
window.addEventListener('resize', hr)
onUnmounted(() => { window.removeEventListener('resize', hr); cc?.dispose(); oc?.dispose(); calCc?.dispose() })
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
  grid-template-columns: 1fr 80px 70px 90px 85px 85px 100px 90px 120px;
  align-items: center; padding: var(--space-3) var(--space-5); gap: var(--space-3);
}
.ht-header span, .ht-row span { white-space: nowrap; }
.ht-header { font-size: var(--text-xs); color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 0.05em; background: var(--color-bg); border-bottom: 1px solid var(--color-border); }
.ht-row { border-bottom: 1px solid var(--color-divider); font-size: var(--text-base); cursor: pointer; transition: background var(--transition-fast); }
.ht-row:hover { background: var(--color-bg); }
.ht-row:last-child { border-bottom: none; }
.ht-empty { text-align: center; padding: var(--space-8); color: var(--color-text-muted); font-size: var(--text-sm); }

.code-text { font-family: var(--font-mono); font-weight: 600; }
.unset { color: var(--color-text-muted); font-style: italic; }

/* Holdings return colors */
.col-ra .up, .col-rr .up, .col-dr .up { color: var(--color-up); font-weight: 600; font-family: var(--font-mono); font-size: var(--text-sm); }
.col-ra .down, .col-rr .down, .col-dr .down { color: var(--color-down); font-weight: 600; font-family: var(--font-mono); font-size: var(--text-sm); }
.col-ra .zero, .col-rr .zero, .col-dr .zero { color: var(--color-text-muted); font-weight: 600; font-family: var(--font-mono); font-size: var(--text-sm); }

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

/* ── Actions Bar ── */
.pf-actions {
  display: flex; align-items: center; gap: var(--space-4);
  background: var(--color-surface); border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-6); margin-bottom: var(--space-6);
  box-shadow: var(--shadow-sm); flex-wrap: wrap;
}

.action-group { display: flex; align-items: center; gap: var(--space-2); }
.action-label {
  font-size: var(--text-xs); color: var(--color-text-secondary);
  font-weight: 500; white-space: nowrap;
}

.date-picker-wrap { display: flex; align-items: center; gap: 4px; }
.date-input {
  height: 30px; padding: 0 var(--space-2);
  border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  font-size: var(--text-xs); font-family: inherit;
  color: var(--color-text-primary); background: var(--color-bg); outline: none;
}
.date-input:focus { border-color: var(--color-primary); }

.action-btn-sm {
  height: 22px; width: 22px; display: inline-flex;
  align-items: center; justify-content: center;
  border: 1px solid var(--color-border); border-radius: 50%;
  background: transparent; cursor: pointer;
  font-size: 14px; color: var(--color-text-muted); font-family: inherit;
}
.action-btn-sm:hover { background: var(--color-bg); color: var(--color-danger); }

.action-divider {
  width: 1px; height: 28px; background: var(--color-divider); flex-shrink: 0;
}

.btn-row { display: flex; gap: 6px; }

.action-btn {
  display: inline-flex; align-items: center; gap: 4px;
  height: 28px; padding: 0 var(--space-3);
  border: 1px solid var(--color-border); background: transparent;
  border-radius: var(--radius-sm); font-size: var(--text-xs);
  font-weight: 500; cursor: pointer; font-family: inherit;
  color: var(--color-text-secondary);
  transition: all var(--transition-fast); white-space: nowrap;
}
.action-btn:hover:not(:disabled) {
  border-color: var(--color-primary); color: var(--color-primary);
  background: var(--color-primary-light);
}
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* ── Date display (read-only) ── */
.date-display {
  font-size: var(--text-sm); font-weight: 500;
  color: var(--color-text-primary); padding: 2px 4px;
}
.date-display.muted { color: var(--color-text-muted); font-style: italic; }
.action-btn-sm.confirm { color: var(--color-primary); border-color: var(--color-primary); }
.action-btn-sm.confirm:hover { background: var(--color-primary-light); }

/* ── Calendar ── */
.cal-year-nav {
  display: flex; align-items: center; justify-content: center;
  gap: var(--space-4); margin-bottom: var(--space-4);
}
.cal-nav-btn {
  width: 32px; height: 32px; border: 1px solid var(--color-border);
  border-radius: 50%; background: transparent; cursor: pointer;
  font-size: 16px; color: var(--color-text-secondary);
  display: flex; align-items: center; justify-content: center;
  font-family: inherit; transition: all var(--transition-fast);
}
.cal-nav-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
.cal-year-label { font-size: var(--text-lg); font-weight: 700; min-width: 80px; text-align: center; }

.cal-section-label {
  font-size: var(--text-sm); font-weight: 600; color: var(--color-text-secondary);
  margin-bottom: var(--space-2); margin-top: var(--space-4);
  padding-bottom: var(--space-1); border-bottom: 1px solid var(--color-divider);
}

/* Yearly month grid */
.cal-month-grid {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2);
}
.cal-month-cell {
  background: var(--color-bg); border-radius: var(--radius-md);
  padding: var(--space-3); text-align: center; cursor: pointer;
  border: 2px solid transparent; transition: all var(--transition-fast);
}
.cal-month-cell:hover:not(.disabled) { border-color: var(--color-border); }
.cal-month-cell.active { border-color: var(--color-primary); background: var(--color-primary-light); }
.cal-month-cell.disabled { opacity: 0.35; cursor: not-allowed; }
.cal-month-cell.bg-up { background: #fef0ef; }
.cal-month-cell.bg-down { background: #f0faf5; }
.cal-month-cell.active.bg-up { background: #fde8e5; }
.cal-month-cell.active.bg-down { background: #e6f7ef; }
.cal-cell-month { font-size: var(--text-sm); font-weight: 700; margin-bottom: 4px; }
.cal-cell-amount { font-family: var(--font-mono); font-size: 11px; font-weight: 600; }
.cal-cell-amount.up { color: var(--color-up); }
.cal-cell-amount.down { color: var(--color-down); }
.cal-cell-amount.zero { color: var(--color-text-muted); }
.cal-cell-rate { font-family: var(--font-mono); font-size: 10px; font-weight: 500; }
.cal-cell-rate.up { color: var(--color-up); }
.cal-cell-rate.down { color: var(--color-down); }
.cal-cell-rate.zero { color: var(--color-text-muted); }
.cal-cell-no-data { font-size: 10px; color: var(--color-text-muted); }

/* Monthly day grid */
.cal-day-header {
  display: grid; grid-template-columns: repeat(7, 1fr);
  gap: 2px; margin-bottom: 4px;
}
.cal-dh-cell {
  text-align: center; font-size: var(--text-xs);
  color: var(--color-text-secondary); font-weight: 500; padding: 4px 0;
}
.cal-day-grid {
  display: grid; grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}
.cal-day-cell {
  background: var(--color-bg); border-radius: var(--radius-sm);
  padding: 4px; text-align: center; cursor: pointer; min-height: 52px;
  border: 1px solid transparent; transition: all var(--transition-fast);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.cal-day-cell:hover:not(.disabled):not(.empty) { border-color: var(--color-border); }
.cal-day-cell.active { border-color: var(--color-primary); background: var(--color-primary-light); }
.cal-day-cell.disabled { opacity: 0.35; cursor: not-allowed; }
.cal-day-cell.empty { background: transparent; cursor: default; }
.cal-day-cell.bg-up { background: #fef0ef; }
.cal-day-cell.bg-down { background: #f0faf5; }
.cal-day-cell.active.bg-up { background: #fde8e5; }
.cal-day-cell.active.bg-down { background: #e6f7ef; }
.cal-cell-day { font-size: var(--text-xs); font-weight: 600; line-height: 1.2; }
.cal-day-cell .cal-cell-amount { font-size: 10px; }
.cal-day-cell .cal-cell-rate { font-size: 9px; }
</style>

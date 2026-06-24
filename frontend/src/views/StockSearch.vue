<template>
  <div>
    <h1 class="page-title">股票搜索</h1>

    <div class="search-box">
      <svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input
        v-model="query"
        type="text"
        placeholder="输入股票代码或名称进行搜索..."
        @input="handleSearch"
      />
      <span v-if="query" class="search-clear" @click="query='';results=[]">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </span>
    </div>

    <div v-if="loading" class="empty-state">
      <div class="spinner"></div>
      <div class="title">搜索中...</div>
    </div>

    <div v-else-if="results.length > 0" class="stock-table-wrap">
      <div class="table-header">
        <span class="col-code">代码</span>
        <span class="col-name">名称</span>
        <span class="col-exchange">交易所</span>
        <span class="col-actions">操作</span>
      </div>
      <div v-for="s in results" :key="s.code" class="table-row">
        <span class="col-code">
          <span class="code-text">{{ s.code }}</span>
        </span>
        <span class="col-name">{{ s.name }}</span>
        <span class="col-exchange">
          <span class="badge" :class="s.exchange === 'SH' ? 'badge--exchange-sh' : 'badge--exchange-sz'">
            {{ s.exchange === 'SH' ? '沪市' : s.exchange === 'SZ' ? '深市' : '北交所' }}
          </span>
        </span>
        <span class="col-actions">
          <button class="btn-sm btn-outline" @click="$router.push(`/stocks/${s.code}/kline`)">K线图</button>
          <button class="btn-sm btn-ghost" @click="addWatchlist(s.code)">+ 自选</button>
        </span>
      </div>
    </div>

    <div v-else-if="query && !loading" class="empty-state">
      <div class="icon">🔍</div>
      <div class="title">未找到相关股票</div>
      <div class="desc">请尝试其他关键词</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { stockApi, watchlistApi } from '../api'
import { ElMessage } from 'element-plus'

const query = ref('')
const results = ref([])
const loading = ref(false)

let timer = null
function handleSearch() {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    if (!query.value.trim()) { results.value = []; return }
    loading.value = true
    try { const { data } = await stockApi.search(query.value.trim()); results.value = data.items }
    finally { loading.value = false }
  }, 300)
}

async function addWatchlist(code) {
  try { await watchlistApi.add(code); ElMessage.success(`已添加 ${code} 到自选`) }
  catch { /* handled */ }
}
</script>

<style scoped>
.search-box {
  position: relative;
  max-width: 480px;
  margin-bottom: var(--space-6);
}
.search-box input {
  width: 100%;
  height: 48px;
  padding: 0 var(--space-4) 0 44px;
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-family: inherit;
  color: var(--color-text-primary);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.search-box input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-light); }
.search-box input::placeholder { color: var(--color-text-muted); }
.search-icon {
  position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
  color: var(--color-text-muted); pointer-events: none;
}
.search-clear {
  position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
  cursor: pointer; color: var(--color-text-muted); padding: 4px;
}

.stock-table-wrap {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.table-header, .table-row {
  display: grid;
  grid-template-columns: 120px 1fr 100px 180px;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  gap: var(--space-3);
}
.table-header {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}
.table-row {
  font-size: var(--text-base);
  border-bottom: 1px solid var(--color-divider);
  transition: background var(--transition-fast);
}
.table-row:last-child { border-bottom: none; }
.table-row:hover { background: #fafbfc; }

.code-text {
  font-family: var(--font-mono);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.badge--exchange-sh { background: #eff6ff; color: #3b82f6; padding: 2px 10px; border-radius: 100px; font-size: var(--text-xs); font-weight: 500; }
.badge--exchange-sz { background: #f0fdf4; color: #22c55e; padding: 2px 10px; border-radius: 100px; font-size: var(--text-xs); font-weight: 500; }

.btn-sm {
  height: 32px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: inherit;
}
.btn-outline {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
}
.btn-outline:hover { border-color: var(--color-primary); color: var(--color-primary); }
.btn-ghost {
  background: transparent;
  border: 1px solid transparent;
  color: var(--color-text-secondary);
}
.btn-ghost:hover { background: var(--color-bg); color: var(--color-text-primary); }

.spinner {
  width: 32px; height: 32px;
  margin: 0 auto var(--space-3);
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>

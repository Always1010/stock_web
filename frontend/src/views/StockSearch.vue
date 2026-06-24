<template>
  <div>
    <h1 class="page-title">股票搜索结果</h1>
    <p v-if="keyword" class="page-subtitle">关键词：{{ keyword }}</p>

    <div v-if="loading" class="empty-state">
      <div class="spinner"></div>
      <div class="title">搜索中...</div>
    </div>

    <div v-else-if="results.length > 0" class="results-wrap">
      <div
        v-for="s in results" :key="s.code"
        class="result-row"
        @click="goKline(s.code)"
      >
        <div class="result-info">
          <span class="result-code">{{ s.code }}</span>
          <span class="result-name">{{ s.name }}</span>
          <span class="result-exchange">{{ s.exchange === 'SH' ? '沪' : s.exchange === 'SZ' ? '深' : '京' }}</span>
        </div>
        <div class="result-price">
          <span v-if="s.latest_close != null" class="result-close">{{ s.latest_close.toFixed(2) }}</span>
          <span v-else class="result-close">--</span>
          <span
            v-if="s.change_pct != null"
            class="result-change"
            :class="{ up: s.change_pct > 0, down: s.change_pct < 0 }"
          >
            {{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
          </span>
          <span v-else class="result-change">--</span>
        </div>
        <button class="result-star" @click.stop="addWatchlist(s.code)" title="加自选">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        </button>
      </div>
    </div>

    <div v-else-if="!loading" class="empty-state">
      <div class="icon">🔍</div>
      <div class="title">{{ keyword ? '未找到相关股票' : '请输入搜索关键词' }}</div>
      <div class="desc">{{ keyword ? '请尝试其他关键词' : '使用顶部搜索栏搜索股票代码或名称' }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { stockApi, watchlistApi } from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const keyword = ref('')
const results = ref([])
const loading = ref(false)

async function doSearch(q) {
  if (!q) { results.value = []; return }
  loading.value = true
  try { const { data } = await stockApi.search(q); results.value = data.items }
  finally { loading.value = false }
}

function goKline(code) {
  router.push(`/stocks/${code}/kline`)
}

onMounted(() => {
  if (route.query.q) {
    keyword.value = route.query.q
    doSearch(route.query.q)
  }
})

watch(() => route.query.q, (newQ) => {
  if (newQ) {
    keyword.value = newQ
    doSearch(newQ)
  }
})

async function addWatchlist(code) {
  try { await watchlistApi.add(code); ElMessage.success(`已添加 ${code} 到自选`) }
  catch { /* handled */ }
}
</script>

<style scoped>
.page-subtitle {
  margin-top: -12px;
  margin-bottom: var(--space-6);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
}

/* ── Results ── */
.results-wrap {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.result-row {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-3) var(--space-5); cursor: pointer;
  border-bottom: 1px solid var(--color-divider);
  transition: background var(--transition-fast);
}
.result-row:last-child { border-bottom: none; }
.result-row:hover { background: var(--color-bg); }

.result-info { flex: 1; min-width: 0; display: flex; align-items: center; gap: var(--space-2); }
.result-code { font-family: var(--font-mono); font-weight: 600; font-size: 14px; }
.result-name { font-size: 14px; color: var(--color-text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.result-exchange {
  font-size: 11px; padding: 1px 6px; border-radius: 3px; flex-shrink: 0;
  background: var(--color-bg); color: var(--color-text-muted);
}

.result-price { display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0; }
.result-close { font-family: var(--font-mono); font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; }
.result-change { font-family: var(--font-mono); font-size: 13px; font-weight: 500; padding: 2px 8px; border-radius: 4px; min-width: 68px; text-align: center; }
.result-change.up { color: #fff; background: var(--color-up); }
.result-change.down { color: #fff; background: var(--color-down); }

.result-star {
  width: 32px; height: 32px; flex-shrink: 0; border: none; background: transparent;
  border-radius: 6px; display: flex; align-items: center; justify-content: center;
  color: var(--color-text-muted); cursor: pointer; transition: all var(--transition-fast);
}
.result-star:hover { background: var(--color-primary-light); color: var(--color-primary); }

/* ── Empty / Loading ── */
.empty-state {
  text-align: center;
  padding: var(--space-16) var(--space-4);
  color: var(--color-text-muted);
}
.empty-state .icon { font-size: 40px; }
.empty-state .title { font-size: var(--text-lg); font-weight: 600; margin-top: var(--space-2); }
.empty-state .desc { font-size: var(--text-sm); margin-top: var(--space-1); }

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

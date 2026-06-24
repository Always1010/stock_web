<template>
  <div class="ssb" ref="rootRef">
    <div class="ssb-input-wrap">
      <svg class="ssb-search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input
        ref="inputRef"
        v-model="query"
        type="text"
        placeholder="搜索股票代码或名称..."
        @focus="onFocus"
        @blur="onBlur"
        @keydown.escape="close"
        @keydown.enter.prevent="handleEnter"
        @keydown.up.prevent="moveUp"
        @keydown.down.prevent="moveDown"
      />
      <span v-if="query" class="ssb-clear" @mousedown.prevent="close()">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </span>
    </div>

    <div v-if="showDropdown" class="ssb-dropdown">
      <div v-if="loading" class="ssb-loading">搜索中...</div>
      <div v-else-if="results.length === 0" class="ssb-empty">无匹配结果</div>
      <div
        v-for="(s, i) in results" :key="s.code"
        class="ssb-row"
        :class="{ highlighted: highlightIndex === i }"
        @mousedown.prevent="selectStock(s)"
      >
        <div class="ssb-info">
          <span class="ssb-code">{{ s.code }}</span>
          <span class="ssb-name">{{ s.name }}</span>
          <span class="ssb-exchange">{{ s.exchange === 'SH' ? '沪' : s.exchange === 'SZ' ? '深' : '京' }}</span>
        </div>
        <div class="ssb-price">
          <span v-if="s.latest_close != null" class="ssb-close">{{ s.latest_close.toFixed(2) }}</span>
          <span v-else class="ssb-close">--</span>
          <span
            v-if="s.change_pct != null"
            class="ssb-change"
            :class="{ up: s.change_pct > 0, down: s.change_pct < 0 }"
          >
            {{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
          </span>
          <span v-else class="ssb-change">--</span>
        </div>
        <button
          class="ssb-star"
          :class="{ watched: watchlistCodes.has(s.code) }"
          @mousedown.prevent.stop="toggleWatchlist(s.code)"
          :title="watchlistCodes.has(s.code) ? '取消自选' : '加自选'"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" :fill="watchlistCodes.has(s.code) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { stockApi, watchlistApi } from '../api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const query = ref('')
const results = ref([])
const loading = ref(false)
const showDropdown = ref(false)
const highlightIndex = ref(-1)
const rootRef = ref(null)
const inputRef = ref(null)
const watchlistCodes = ref(new Set())

let timer = null

onMounted(async () => {
  try {
    const { data } = await watchlistApi.list()
    watchlistCodes.value = new Set(data.items.map(w => w.code))
  } catch { /* ignore */ }
})

watch(query, () => {
  clearTimeout(timer)
  highlightIndex.value = -1
  if (!query.value.trim()) { results.value = []; showDropdown.value = false; return }
  timer = setTimeout(async () => {
    loading.value = true
    showDropdown.value = true
    try {
      const { data } = await stockApi.search(query.value.trim(), 10)
      results.value = data.items
      highlightIndex.value = -1
    } finally {
      loading.value = false
    }
  }, 200)
})

function onFocus() { if (query.value.trim()) showDropdown.value = true }

function onBlur() { setTimeout(() => { showDropdown.value = false }, 150) }

function close() {
  clearTimeout(timer)
  showDropdown.value = false
  query.value = ''
  results.value = []
  highlightIndex.value = -1
}

function selectStock(s) {
  close()
  router.push(`/stocks/${s.code}/kline`)
}

function moveUp() {
  if (!showDropdown.value || results.value.length === 0) return
  highlightIndex.value = highlightIndex.value <= 0 ? results.value.length - 1 : highlightIndex.value - 1
  scrollToHighlighted()
}

function moveDown() {
  if (!showDropdown.value || results.value.length === 0) return
  highlightIndex.value = highlightIndex.value >= results.value.length - 1 ? 0 : highlightIndex.value + 1
  scrollToHighlighted()
}

function handleEnter() {
  if (!showDropdown.value || results.value.length === 0) {
    // No dropdown open or no results — navigate to search page
    if (query.value.trim()) {
      router.push({ path: '/stocks', query: { q: query.value.trim() } })
      close()
    }
    return
  }
  if (highlightIndex.value >= 0 && highlightIndex.value < results.value.length) {
    selectStock(results.value[highlightIndex.value])
  } else {
    // Enter without arrow-key selection → search page with all results
    router.push({ path: '/stocks', query: { q: query.value.trim() } })
    close()
  }
}

function scrollToHighlighted() {
  nextTick(() => {
    const el = rootRef.value?.querySelector('.ssb-row.highlighted')
    el?.scrollIntoView({ block: 'nearest' })
  })
}

async function toggleWatchlist(code) {
  if (watchlistCodes.value.has(code)) {
    try {
      await watchlistApi.remove(code)
      watchlistCodes.value.delete(code)
      ElMessage.success(`已取消自选 ${code}`)
    } catch { /* handled */ }
  } else {
    try {
      await watchlistApi.add(code)
      watchlistCodes.value.add(code)
      ElMessage.success(`已添加 ${code}`)
    } catch { /* handled */ }
  }
}
</script>

<style scoped>
.ssb { position: relative; width: 100%; max-width: 400px; }
.ssb-input-wrap { position: relative; display: flex; align-items: center; }
.ssb-search-icon { position: absolute; left: 10px; color: var(--color-text-muted); pointer-events: none; }
.ssb-input-wrap input {
  width: 100%; height: 34px; padding: 0 32px 0 32px;
  background: var(--color-bg); border: 1px solid var(--color-border);
  border-radius: 8px; font-size: 13px; font-family: inherit;
  color: var(--color-text-primary); outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.ssb-input-wrap input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 2px var(--color-primary-light); }
.ssb-input-wrap input::placeholder { color: var(--color-text-muted); }
.ssb-clear {
  position: absolute; right: 8px; cursor: pointer; padding: 4px;
  color: var(--color-text-muted); display: flex;
}
.ssb-clear:hover { color: var(--color-text-secondary); }

/* ── Dropdown ── */
.ssb-dropdown {
  position: absolute; top: 40px; left: 0; right: 0;
  background: var(--color-surface); border-radius: 10px;
  box-shadow: var(--shadow-xl); border: 1px solid var(--color-border);
  max-height: 420px; overflow-y: auto; z-index: 200;
}
.ssb-loading, .ssb-empty {
  padding: var(--space-5) var(--space-4);
  text-align: center; font-size: var(--text-sm); color: var(--color-text-muted);
}

.ssb-row {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-3) var(--space-4); cursor: pointer;
  border-bottom: 1px solid var(--color-divider);
  transition: background var(--transition-fast);
}
.ssb-row:last-child { border-bottom: none; }
.ssb-row:hover { background: var(--color-bg); }
.ssb-row.highlighted { background: var(--color-primary-light); }

.ssb-info { flex: 1; min-width: 0; display: flex; align-items: center; gap: var(--space-2); }
.ssb-code { font-family: var(--font-mono); font-weight: 600; font-size: 13px; }
.ssb-name { font-size: 13px; color: var(--color-text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ssb-exchange {
  font-size: 10px; padding: 1px 5px; border-radius: 3px; flex-shrink: 0;
  background: var(--color-bg); color: var(--color-text-muted);
}

.ssb-price { display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0; }
.ssb-close { font-family: var(--font-mono); font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }
.ssb-change { font-family: var(--font-mono); font-size: 12px; font-weight: 500; padding: 1px 6px; border-radius: 4px; min-width: 60px; text-align: center; }
.ssb-change.up { color: #fff; background: var(--color-up); }
.ssb-change.down { color: #fff; background: var(--color-down); }

.ssb-star {
  width: 30px; height: 30px; flex-shrink: 0; border: none; background: transparent;
  border-radius: 6px; display: flex; align-items: center; justify-content: center;
  color: var(--color-text-muted); cursor: pointer; transition: all var(--transition-fast);
}
.ssb-star:hover { background: var(--color-primary-light); color: var(--color-primary); }
.ssb-star.watched { color: #f59e0b; }
.ssb-star.watched:hover { color: #d97706; }
</style>

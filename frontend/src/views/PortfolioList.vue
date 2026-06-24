<template>
  <div>
    <div class="flex-between" style="margin-bottom:var(--space-6)">
      <h1 class="page-title" style="margin-bottom:0">📊 我的组合</h1>
      <button class="btn-create" @click="$router.push('/portfolios/create')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        创建组合
      </button>
    </div>

    <div v-loading="loading">
      <div v-if="portfolios.length > 0" class="pf-grid">
        <div v-for="p in portfolios" :key="p.code" class="pf-card" @click="$router.push(`/portfolios/${p.code}`)">
          <div class="pf-card-top">
            <div>
              <div class="pf-name">{{ p.name }}</div>
              <div class="pf-code">{{ p.code }}</div>
            </div>
            <div class="pf-status">
              <span :class="['badge', (p.latest_return_rate ?? 0) >= 0 ? 'badge--up' : 'badge--down']">
                {{ p.latest_return_rate != null ? ((p.latest_return_rate * 100).toFixed(2) + '%') : '--' }}
              </span>
            </div>
          </div>
          <div class="pf-divider"></div>
          <div class="pf-card-bottom">
            <div>
              <div class="stat-label">最新净值</div>
              <div class="stat-val">¥{{ p.latest_nav != null ? p.latest_nav.toFixed(2) : '--' }}</div>
            </div>
            <div>
              <div class="stat-label">创建时间</div>
              <div class="stat-val-sm">{{ p.created_at?.slice(0,10) }}</div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <div class="icon">📊</div>
        <div class="title">暂无组合</div>
        <div class="desc">创建你的第一个模拟投资组合</div>
        <button class="btn-create" style="margin-top:var(--space-4)" @click="$router.push('/portfolios/create')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          创建第一个组合
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { portfolioApi } from '../api'

const portfolios = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try { const { data } = await portfolioApi.list(); portfolios.value = data }
  finally { loading.value = false }
})
</script>

<style scoped>
.btn-create {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 var(--space-5);
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all var(--transition-fast);
}
.btn-create:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(37,99,235,0.35); }

.pf-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}

.pf-card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--transition-fast);
}
.pf-card:hover { border-color: var(--color-border); box-shadow: var(--shadow-md); transform: translateY(-2px); }

.pf-card-top { display: flex; justify-content: space-between; align-items: flex-start; }
.pf-name { font-size: var(--text-lg); font-weight: 600; color: var(--color-text-primary); }
.pf-code { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--color-text-muted); margin-top: 2px; }
.pf-divider { height: 1px; background: var(--color-divider); margin: var(--space-4) 0; }
.pf-card-bottom { display: flex; gap: var(--space-8); }
.stat-val { font-family: var(--font-mono); font-size: var(--text-xl); font-weight: 700; font-variant-numeric: tabular-nums; }
.stat-val-sm { font-size: var(--text-sm); color: var(--color-text-secondary); }
</style>

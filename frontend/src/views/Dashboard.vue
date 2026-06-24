<template>
  <div>
    <div class="welcome">
      <div>
        <h1 class="page-title" style="margin-bottom:4px">{{ greeting }}，{{ auth.user?.username }}</h1>
        <p class="page-subtitle" style="margin-top:0;margin-bottom:0">随时掌握你的模拟投资动态</p>
      </div>
    </div>

    <!-- Stat cards -->
    <div class="stat-grid">
      <div class="stat-card" @click="$router.push('/watchlist')">
        <div class="stat-icon" style="background:var(--color-primary-light)">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        </div>
        <div class="stat-label">自选股</div>
        <div class="stat-number">{{ watchlistCount }}</div>
        <div class="stat-hint">只</div>
      </div>

      <div class="stat-card" @click="$router.push('/portfolios')">
        <div class="stat-icon" style="background:#fef3c7">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
        </div>
        <div class="stat-label">我的组合</div>
        <div class="stat-number">{{ portfolioCount }}</div>
        <div class="stat-hint">个</div>
      </div>

      <div class="stat-card" @click="$router.push('/stocks')">
        <div class="stat-icon" style="background:#f0fdf4">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        </div>
        <div class="stat-label">A 股市场</div>
        <div class="stat-number">{{ stockCount }}</div>
        <div class="stat-hint">只股票</div>
      </div>
    </div>

    <!-- Quick actions -->
    <div class="section-header mt-6">
      <h3 class="section-title">快捷操作</h3>
    </div>
    <div class="action-grid">
      <button class="action-card" @click="$router.push('/stocks')">
        <div class="action-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        </div>
        <span>搜索股票</span>
        <small>查找并查看 K 线图表</small>
      </button>

      <button class="action-card" @click="$router.push('/portfolios/create')">
        <div class="action-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </div>
        <span>创建组合</span>
        <small>构建你的模拟投资组合</small>
      </button>

      <button class="action-card" @click="$router.push('/watchlist')">
        <div class="action-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        </div>
        <span>查看自选</span>
        <small>管理你关注的自选股票</small>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { stockApi, watchlistApi, portfolioApi } from '../api'

const auth = useAuthStore()
const watchlistCount = ref(0)
const portfolioCount = ref(0)
const stockCount = ref(0)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
})

onMounted(async () => {
  try {
    const [w, p, s] = await Promise.all([
      watchlistApi.list(), portfolioApi.list(), stockApi.search(''),
    ])
    watchlistCount.value = w.data.items.length
    portfolioCount.value = p.data.length
    stockCount.value = s.data.items.length
  } catch { /* ignore */ }
})
</script>

<style scoped>
.welcome { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--space-8); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}
.stat-card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
}
.stat-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-border);
  transform: translateY(-2px);
}
.stat-icon {
  width: 40px; height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-3);
}
.stat-card .stat-label {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 2px;
}
.stat-card .stat-number {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.stat-hint {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}
.action-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  cursor: pointer;
  text-align: center;
  transition: all var(--transition-fast);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  font-family: inherit;
}
.action-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.action-card .action-icon {
  width: 48px; height: 48px;
  background: var(--color-bg);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-1);
  transition: all var(--transition-fast);
}
.action-card:hover .action-icon {
  background: var(--color-primary-light);
  color: var(--color-primary);
}
.action-card span {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text-primary);
}
.action-card small {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}
</style>

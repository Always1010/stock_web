<template>
  <div class="shell">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ collapsed }">
      <div class="sidebar-brand" @click="collapsed = !collapsed" :title="collapsed ? '展开菜单' : '收起菜单'">
        <div class="brand-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
        </div>
        <span class="brand-text">StockSim</span>
        <svg class="brand-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline v-if="collapsed" points="9 18 15 12 9 6"/><polyline v-else points="15 18 9 12 15 6"/></svg>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/" class="nav-item" exact-active-class="active">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          </span>
          <span class="nav-label">首页</span>
        </router-link>

        <router-link to="/market" class="nav-item" active-class="active">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
          </span>
          <span class="nav-label">市场行情</span>
        </router-link>

        <router-link to="/watchlist" class="nav-item" active-class="active">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          </span>
          <span class="nav-label">我的自选</span>
        </router-link>

        <router-link to="/portfolios" class="nav-item" active-class="active">
          <span class="nav-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          </span>
          <span class="nav-label">我的组合</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="user-card">
          <div class="user-avatar">{{ auth.user?.username?.[0]?.toUpperCase() }}</div>
          <div v-if="!collapsed">
            <div class="user-name">{{ auth.user?.username }}</div>
            <div class="user-role">交易员</div>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main -->
    <div class="main" :class="{ collapsed }">
      <header class="topbar">
        <div class="topbar-left">
          <span class="topbar-greeting">{{ greeting }}</span>
        </div>
        <div class="topbar-center">
          <StockSearchBar />
        </div>
        <div class="topbar-right">
          <button class="btn-icon" @click="$router.push('/portfolios/create')" title="创建组合">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
          <button class="btn-icon" @click="handleLogout" title="退出登录">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          </button>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import StockSearchBar from './StockSearchBar.vue'

const router = useRouter()
const auth = useAuthStore()
const collapsed = ref(false)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.shell { display: flex; min-height: 100vh; background: var(--color-bg); }

/* ── Sidebar ── */
.sidebar {
  width: var(--sidebar-width);
  background: var(--color-sidebar);
  display: flex; flex-direction: column;
  position: fixed; top: 0; left: 0; bottom: 0; z-index: 100;
  transition: width var(--transition-base);
}
.sidebar.collapsed { width: 64px; }

.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 20px 16px 20px;
  cursor: pointer; user-select: none; overflow: hidden;
  transition: padding var(--transition-base);
}
.collapsed .sidebar-brand { padding: 20px 16px; justify-content: center; }
.brand-icon {
  width: 32px; height: 32px; flex-shrink: 0;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #fff;
}
.brand-text {
  font-size: 16px; font-weight: 700; color: #fff;
  letter-spacing: 0.02em; white-space: nowrap;
  transition: opacity var(--transition-base);
}
.collapsed .brand-text { opacity: 0; width: 0; overflow: hidden; }
.brand-arrow {
  color: var(--color-sidebar-text); flex-shrink: 0; opacity: 0.6;
  transition: opacity var(--transition-base); margin-left: auto;
}
.collapsed .brand-arrow { opacity: 0; width: 0; overflow: hidden; }

.sidebar-nav { flex: 1; padding: 0 12px; display: flex; flex-direction: column; gap: 2px; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px;
  color: var(--color-sidebar-text); font-size: 14px; font-weight: 500;
  transition: all var(--transition-fast); text-decoration: none;
  overflow: hidden; white-space: nowrap;
}
.nav-item:hover { background: var(--color-sidebar-hover); color: #d1d5db; }
.nav-item.active { background: rgba(59, 130, 246, 0.15); color: var(--color-sidebar-active); }
.nav-icon { display: flex; align-items: center; width: 20px; flex-shrink: 0; opacity: 0.7; }
.nav-item.active .nav-icon { opacity: 1; }
.nav-label { transition: opacity var(--transition-base); }
.collapsed .nav-label { opacity: 0; width: 0; overflow: hidden; }

/* Sidebar footer */
.sidebar-footer { padding: 12px; border-top: 1px solid rgba(255,255,255,0.06); }
.user-card { display: flex; align-items: center; gap: 10px; padding: 8px; border-radius: 8px; overflow: hidden; }
.user-avatar {
  width: 32px; height: 32px; flex-shrink: 0; border-radius: 8px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 600;
}
.user-name { font-size: 13px; color: #e5e7eb; font-weight: 500; white-space: nowrap; }
.user-role { font-size: 11px; color: var(--color-sidebar-text); white-space: nowrap; }

/* ── Main (width calc to match collapsed state) ── */
.main {
  margin-left: var(--sidebar-width);
  width: calc(100vw - var(--sidebar-width));
  display: flex; flex-direction: column; min-height: 100vh;
  transition: margin-left var(--transition-base), width var(--transition-base);
  overflow-x: hidden;
}
.main.collapsed {
  margin-left: 64px;
  width: calc(100vw - 64px);
}

/* ── Topbar ── */
.topbar {
  height: var(--header-height); background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 var(--space-8); position: sticky; top: 0; z-index: 50;
}
.topbar-left { width: 100px; flex-shrink: 0; }
.topbar-center { flex: 1; display: flex; justify-content: center; padding: 0 var(--space-4); }
.topbar-right { width: 100px; flex-shrink: 0; display: flex; gap: 4px; justify-content: flex-end; }
.topbar-greeting { font-size: var(--text-sm); color: var(--color-text-secondary); font-weight: 500; }

.btn-icon {
  width: 36px; height: 36px; border: none; background: transparent;
  border-radius: 8px; display: flex; align-items: center; justify-content: center;
  color: var(--color-text-secondary); cursor: pointer; transition: all var(--transition-fast);
}
.btn-icon:hover { background: var(--color-bg); color: var(--color-text-primary); }

/* ── Content ── */
.content { flex: 1; padding: var(--space-8); }
</style>

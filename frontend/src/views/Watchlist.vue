<template>
  <div>
    <h1 class="page-title">⭐ 我的自选</h1>

    <div v-if="loading" class="empty-state">
      <div class="spinner"></div>
      <div class="title">加载中...</div>
    </div>

    <div v-else-if="items.length > 0" class="wl-table-wrap">
      <div class="wl-header">
        <span class="col-code">代码</span>
        <span class="col-name">名称</span>
        <span class="col-exchange">市场</span>
        <span class="col-price">最新价</span>
        <span class="col-actions">操作</span>
      </div>
      <div v-for="s in items" :key="s.id" class="wl-row" @click="$router.push(`/stocks/${s.code}/kline`)">
        <span class="col-code">
          <span class="code-text">{{ s.code }}</span>
        </span>
        <span class="col-name">{{ s.name }}</span>
        <span class="col-exchange">
          <span :class="['market-tag', s.exchange === 'SH' ? 'sh' : 'sz']">
            {{ s.exchange === 'SH' ? '沪' : s.exchange === 'SZ' ? '深' : '京' }}
          </span>
        </span>
        <span class="col-price">
          <span class="price-val">{{ s.latest_close ? s.latest_close.toFixed(2) : '--' }}</span>
        </span>
        <span class="col-actions" @click.stop>
          <button class="btn-mini danger" @click="handleRemove(s.code)">删除</button>
        </span>
      </div>
    </div>

    <div v-else class="empty-state">
      <div class="icon">⭐</div>
      <div class="title">暂无自选股</div>
      <div class="desc">去 <router-link to="/stocks">股票搜索</router-link> 添加你关注的股票</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { watchlistApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const items = ref([])
const loading = ref(false)

async function fetch() {
  loading.value = true
  try { const { data } = await watchlistApi.list(); items.value = data.items }
  finally { loading.value = false }
}

async function handleRemove(code) {
  try { await ElMessageBox.confirm('确定移除此自选股？'); await watchlistApi.remove(code); ElMessage.success('已删除'); fetch() }
  catch { /* cancelled */ }
}

onMounted(fetch)
</script>

<style scoped>
.wl-table-wrap {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.wl-header, .wl-row {
  display: grid;
  grid-template-columns: 120px 1fr 80px 140px 100px;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  gap: var(--space-3);
}
.wl-header {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}
.wl-row {
  font-size: var(--text-base);
  border-bottom: 1px solid var(--color-divider);
  transition: background var(--transition-fast);
  cursor: pointer;
}
.wl-row:hover { background: #fafbfc; }
.wl-row:last-child { border-bottom: none; }

.code-text {
  font-family: var(--font-mono);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.price-val {
  font-family: var(--font-mono);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.market-tag {
  display: inline-block;
  width: 28px; height: 20px;
  line-height: 20px;
  text-align: center;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.market-tag.sh { background: #eff6ff; color: #3b82f6; }
.market-tag.sz { background: #f0fdf4; color: #22c55e; }

.btn-mini {
  height: 28px;
  padding: 0 var(--space-3);
  border-radius: 4px;
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  border: none;
  font-family: inherit;
  transition: all var(--transition-fast);
}
.btn-mini.danger { background: transparent; color: var(--color-text-muted); }
.btn-mini.danger:hover { background: #fef2f2; color: var(--color-danger); }

.spinner {
  width: 32px; height: 32px; margin: 0 auto var(--space-3);
  border: 3px solid var(--color-border); border-top-color: var(--color-primary);
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>

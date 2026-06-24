<template>
  <div>
    <h1 class="page-title">创建组合</h1>
    <div class="create-card">
      <div class="create-icon">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
      </div>
      <h2 class="create-title">新建投资组合</h2>
      <p class="create-desc">组合将从你自选股中选取，每天收盘后自动更新净值</p>

      <form class="create-form" @submit.prevent="handleCreate">
        <div class="field">
          <label>组合名称</label>
          <input v-model="form.name" type="text" placeholder="例如：我的成长组合" autofocus />
        </div>
        <div class="create-actions">
          <button class="btn-cancel" type="button" @click="$router.back()">取消</button>
          <button class="btn-create" type="submit" :disabled="!form.name.trim() || loading">
            <span v-if="loading" class="spinner-sm"></span>
            <span v-else>创建组合</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { portfolioApi } from '../api'

const router = useRouter()
const loading = ref(false)
const form = ref({ name: '' })

async function handleCreate() {
  if (!form.value.name.trim()) return
  loading.value = true
  try { const { data } = await portfolioApi.create({ name: form.value.name.trim() }); router.push(`/portfolios/${data.code}`) }
  finally { loading.value = false }
}
</script>

<style scoped>
.create-card {
  max-width: 480px;
  background: var(--color-surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  padding: var(--space-10);
  text-align: center;
}
.create-icon {
  width: 64px; height: 64px;
  margin: 0 auto var(--space-4);
  background: var(--color-primary-light);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
}
.create-title { font-size: var(--text-xl); font-weight: 700; margin-bottom: var(--space-1); }
.create-desc { font-size: var(--text-sm); color: var(--color-text-secondary); margin-bottom: var(--space-8); }

.create-form { text-align: left; }
.field { margin-bottom: var(--space-6); }
.field label { display: block; font-size: var(--text-sm); font-weight: 500; margin-bottom: 6px; }
.field input {
  width: 100%; height: 44px; padding: 0 var(--space-3);
  background: var(--color-bg); border: 1.5px solid var(--color-border);
  border-radius: var(--radius-sm); font-size: var(--text-base); font-family: inherit;
  outline: none; transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.field input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-light); }

.create-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.btn-cancel {
  height: 40px; padding: 0 var(--space-5);
  background: transparent; border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); font-size: var(--text-base); font-weight: 500;
  cursor: pointer; font-family: inherit; color: var(--color-text-secondary);
  transition: all var(--transition-fast);
}
.btn-cancel:hover { background: var(--color-bg); }
.btn-create {
  height: 40px; padding: 0 var(--space-5);
  background: linear-gradient(135deg, #3b82f6, #2563eb); color: #fff;
  border: none; border-radius: var(--radius-sm); font-size: var(--text-base); font-weight: 600;
  cursor: pointer; font-family: inherit; transition: all var(--transition-fast);
}
.btn-create:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(37,99,235,0.35); }
.btn-create:disabled { opacity: 0.5; cursor: not-allowed; }
.spinner-sm { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; display: inline-block; animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>

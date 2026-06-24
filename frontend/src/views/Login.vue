<template>
  <div class="auth-shell">
    <div class="auth-card">
      <div class="auth-brand">
        <div class="brand-mark">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
        </div>
        <h1>StockSim</h1>
        <p>专业 A 股模拟交易平台</p>
      </div>

      <form class="auth-form" @submit.prevent="handleLogin">
        <div class="field">
          <label>用户名</label>
          <input v-model="form.username" type="text" placeholder="请输入用户名" autocomplete="username" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="form.password" type="password" placeholder="请输入密码" autocomplete="current-password" />
        </div>
        <button class="btn-primary" type="submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span v-else>登 录</span>
        </button>
      </form>

      <div class="auth-footer">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = ref({ username: '', password: '' })

async function handleLogin() {
  if (!form.value.username || !form.value.password) return
  loading.value = true
  try { await auth.login(form.value.username, form.value.password); router.push('/') }
  catch { /* interceptor handles */ }
  finally { loading.value = false }
}
</script>

<style scoped>
.auth-shell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, rgba(99,102,241,0.04) 0%, transparent 50%),
    var(--color-bg);
  padding: var(--space-6);
}

.auth-card {
  width: 400px;
  background: var(--color-surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  padding: var(--space-10) var(--space-8);
}

.auth-brand {
  text-align: center;
  margin-bottom: var(--space-8);
}
.brand-mark {
  width: 52px; height: 52px;
  margin: 0 auto var(--space-4);
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.auth-brand h1 {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
}
.auth-brand p {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.field {
  margin-bottom: var(--space-4);
}
.field label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 6px;
}
.field input {
  width: 100%;
  height: 44px;
  padding: 0 var(--space-3);
  background: var(--color-bg);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  font-family: var(--font-family);
  color: var(--color-text-primary);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.field input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}
.field input::placeholder { color: var(--color-text-muted); }

.btn-primary {
  width: 100%;
  height: 44px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: var(--space-2);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37,99,235,0.35);
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.spinner {
  width: 20px; height: 20px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.auth-footer {
  text-align: center;
  margin-top: var(--space-6);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
.auth-footer a { font-weight: 500; }
</style>

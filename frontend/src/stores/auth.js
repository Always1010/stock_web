import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)

  async function login(username, password) {
    const { data } = await authApi.login({ username, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)

    const { data: userData } = await authApi.me()
    user.value = userData
    localStorage.setItem('user', JSON.stringify(userData))
  }

  async function register(username, password) {
    const { data } = await authApi.register({ username, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)

    const { data: userData } = await authApi.me()
    user.value = userData
    localStorage.setItem('user', JSON.stringify(userData))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, login, register, logout }
})

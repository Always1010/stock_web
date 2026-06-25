import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// Request interceptor: inject JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.hash = '#/login'
    }
    return Promise.reject(error)
  }
)

// ── Auth ──────────────────────────────────────────
export const authApi = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
}

// ── Stocks ────────────────────────────────────────
export const stockApi = {
  search: (q, limit) => api.get('/stocks', { params: { q, ...(limit ? { limit } : {}) } }),
  detail: (code) => api.get(`/stocks/${code}`),
  kline: (code, start, end) => api.get(`/stocks/${code}/kline`, { params: { start, end } }),
  refresh: (code) => api.post(`/stocks/${code}/refresh`),
}

// ── Watchlist ─────────────────────────────────────
export const watchlistApi = {
  list: () => api.get('/watchlist'),
  add: (code) => api.post(`/watchlist/${code}`),
  remove: (code) => api.delete(`/watchlist/${code}`),
}

// ── Portfolios ────────────────────────────────────
export const portfolioApi = {
  list: () => api.get('/portfolios'),
  create: (data) => api.post('/portfolios', data),
  detail: (code) => api.get(`/portfolios/${code}`),
  update: (code, data) => api.put(`/portfolios/${code}`, data),
  delete: (code) => api.delete(`/portfolios/${code}`),
  addHolding: (code, data) => api.post(`/portfolios/${code}/holdings`, data),
  updateHolding: (code, holdingId, data) => api.put(`/portfolios/${code}/holdings/${holdingId}`, data),
  removeHolding: (code, holdingId) => api.delete(`/portfolios/${code}/holdings/${holdingId}`),
  setCost: (code, holdingId, data) => api.post(`/portfolios/${code}/holdings/${holdingId}/set-cost`, data),
  nav: (code, start, end) => api.get(`/portfolios/${code}/nav`, { params: { start, end } }),
  dailyReturns: (code, year) => api.get(`/portfolios/${code}/daily-returns`, { params: { year } }),
  contributions: (code, start, end) => api.get(`/portfolios/${code}/contributions`, { params: { start, end } }),
}

// ── Market ────────────────────────────────────────
export const marketApi = {
  refreshIndex: (code) => api.post(`/market/indices/${code}/refresh`),
}

export default api

import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    component: () => import('../components/AppLayout.vue'),
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
      },
      {
        path: 'stocks',
        name: 'StockSearch',
        component: () => import('../views/StockSearch.vue'),
      },
      {
        path: 'stocks/:code/kline',
        name: 'KlineChart',
        component: () => import('../views/KlineChart.vue'),
      },
      {
        path: 'watchlist',
        name: 'Watchlist',
        component: () => import('../views/Watchlist.vue'),
      },
      {
        path: 'portfolios',
        name: 'PortfolioList',
        component: () => import('../views/PortfolioList.vue'),
      },
      {
        path: 'portfolios/create',
        name: 'PortfolioCreate',
        component: () => import('../views/PortfolioCreate.vue'),
      },
      {
        path: 'portfolios/:code',
        name: 'PortfolioDetail',
        component: () => import('../views/PortfolioDetail.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// Auth guard
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.guest) {
    if (token) return next('/')
    return next()
  }
  if (!token) return next('/login')
  next()
})

export default router

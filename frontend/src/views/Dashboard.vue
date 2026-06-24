<template>
  <div>
    <h2>欢迎，{{ auth.user?.username }}</h2>
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat" @click="$router.push('/watchlist')">
            <div class="stat-label">自选股</div>
            <div class="stat-value">{{ watchlistCount }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat" @click="$router.push('/portfolios')">
            <div class="stat-label">我的组合</div>
            <div class="stat-value">{{ portfolioCount }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat" @click="$router.push('/stocks')">
            <div class="stat-label">A股总数</div>
            <div class="stat-value">{{ stockCount }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <h3 style="margin-top:30px">快捷操作</h3>
    <el-space wrap>
      <el-button type="primary" @click="$router.push('/stocks')">🔍 搜索股票</el-button>
      <el-button type="success" @click="$router.push('/portfolios/create')">📊 创建组合</el-button>
      <el-button @click="$router.push('/watchlist')">⭐ 查看自选</el-button>
    </el-space>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { stockApi, watchlistApi, portfolioApi } from '../api'

const auth = useAuthStore()
const watchlistCount = ref(0)
const portfolioCount = ref(0)
const stockCount = ref(0)

onMounted(async () => {
  try {
    const [w, p, s] = await Promise.all([
      watchlistApi.list(),
      portfolioApi.list(),
      stockApi.search(''),
    ])
    watchlistCount.value = w.data.items.length
    portfolioCount.value = p.data.length
    stockCount.value = s.data.items.length
  } catch (e) { /* ignore */ }
})
</script>

<style scoped>
.stat { cursor: pointer; text-align: center; padding: 10px 0; }
.stat-label { font-size: 14px; color: #909399; }
.stat-value { font-size: 36px; font-weight: bold; color: #303133; margin-top: 8px; }
</style>

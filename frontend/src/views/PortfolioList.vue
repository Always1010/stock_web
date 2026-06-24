<template>
  <div>
    <div class="page-header">
      <h2>📊 我的组合</h2>
      <el-button type="primary" @click="$router.push('/portfolios/create')">创建组合</el-button>
    </div>

    <el-row :gutter="20">
      <el-col v-for="p in portfolios" :key="p.code" :span="8" style="margin-bottom:20px">
        <el-card shadow="hover" @click="$router.push(`/portfolios/${p.code}`)" style="cursor:pointer">
          <div class="pf-name">{{ p.name }}</div>
          <div class="pf-code">{{ p.code }}</div>
          <el-divider />
          <el-row>
            <el-col :span="12">
              <div class="pf-label">最新净值</div>
              <div class="pf-value">¥{{ p.latest_nav ? p.latest_nav.toFixed(2) : '--' }}</div>
            </el-col>
            <el-col :span="12">
              <div class="pf-label">累计收益率</div>
              <div :style="{color: p.latest_return_rate >= 0 ? '#f56c6c' : '#67c23a'}" class="pf-value">
                {{ p.latest_return_rate != null ? (p.latest_return_rate * 100).toFixed(2) + '%' : '--' }}
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!loading && portfolios.length === 0" description="暂无组合" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { portfolioApi } from '../api'

const portfolios = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await portfolioApi.list()
    portfolios.value = data
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.pf-name { font-size: 16px; font-weight: bold; }
.pf-code { color: #909399; font-size: 13px; margin-top: 4px; }
.pf-label { font-size: 12px; color: #909399; }
.pf-value { font-size: 18px; font-weight: bold; margin-top: 4px; }
</style>

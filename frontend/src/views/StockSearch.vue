<template>
  <div>
    <h2>股票搜索</h2>
    <el-input
      v-model="query"
      placeholder="输入股票代码或名称搜索"
      clearable
      @input="handleSearch"
      style="max-width:400px;margin-bottom:20px"
    >
      <template #prefix>🔍</template>
    </el-input>

    <el-table :data="results" border stripe v-loading="loading" empty-text="请输入搜索条件">
      <el-table-column prop="code" label="代码" width="120" />
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column prop="exchange" label="交易所" width="100">
        <template #default="{ row }">
          <el-tag :type="row.exchange==='SH'?'':'success'" size="small">
            {{ row.exchange === 'SH' ? '上海' : row.exchange === 'SZ' ? '深圳' : '北京' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="$router.push(`/stocks/${row.code}/kline`)">
            查看K线
          </el-button>
          <el-button size="small" @click="addWatchlist(row.code)">加自选</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { stockApi, watchlistApi } from '../api'
import { ElMessage } from 'element-plus'

const query = ref('')
const results = ref([])
const loading = ref(false)

let timer = null
function handleSearch() {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    if (!query.value.trim()) { results.value = []; return }
    loading.value = true
    try {
      const { data } = await stockApi.search(query.value.trim())
      results.value = data.items
    } finally {
      loading.value = false
    }
  }, 300)
}

async function addWatchlist(code) {
  try {
    await watchlistApi.add(code)
    ElMessage.success(`已添加 ${code} 到自选`)
  } catch (e) { /* handled by interceptor */ }
}
</script>

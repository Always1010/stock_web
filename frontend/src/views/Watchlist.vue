<template>
  <div>
    <h2>⭐ 我的自选</h2>
    <el-table :data="items" border stripe v-loading="loading" empty-text="暂无自选股">
      <el-table-column prop="code" label="代码" width="120" />
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column prop="exchange" label="交易所" width="100">
        <template #default="{ row }">
          <el-tag :type="row.exchange==='SH'?'':'success'" size="small">
            {{ row.exchange === 'SH' ? '上海' : row.exchange === 'SZ' ? '深圳' : '北京' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最新价" width="120">
        <template #default="{ row }">
          {{ row.latest_close ? '¥' + row.latest_close.toFixed(2) : '--' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="$router.push(`/stocks/${row.code}/kline`)">
            K线
          </el-button>
          <el-button size="small" type="danger" @click="handleRemove(row.code)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { watchlistApi } from '../api'
import { ElMessage } from 'element-plus'

const items = ref([])
const loading = ref(false)

async function fetchData() {
  loading.value = true
  try {
    const { data } = await watchlistApi.list()
    items.value = data.items
  } finally {
    loading.value = false
  }
}

async function handleRemove(code) {
  await watchlistApi.remove(code)
  ElMessage.success('已删除')
  fetchData()
}

onMounted(fetchData)
</script>

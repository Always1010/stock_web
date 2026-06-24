<template>
  <div>
    <h2>创建组合</h2>
    <el-card style="max-width:500px">
      <el-form :model="form" label-position="top" @submit.prevent="handleCreate">
        <el-form-item label="组合名称">
          <el-input v-model="form.name" placeholder="例如：我的成长组合" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading">创建</el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
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
  try {
    const { data } = await portfolioApi.create({ name: form.value.name.trim() })
    router.push(`/portfolios/${data.code}`)
  } finally {
    loading.value = false
  }
}
</script>

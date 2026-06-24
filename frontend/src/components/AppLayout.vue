<template>
  <el-container style="min-height:100vh">
    <el-aside width="200px" style="background:#304156">
      <div class="logo">📈 股票模拟</div>
      <el-menu
        :default-active="route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item index="/">
          <span>🏠 首页</span>
        </el-menu-item>
        <el-menu-item index="/stocks">
          <span>🔍 股票搜索</span>
        </el-menu-item>
        <el-menu-item index="/watchlist">
          <span>⭐ 我的自选</span>
        </el-menu-item>
        <el-menu-item index="/portfolios">
          <span>📊 我的组合</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="display:flex;justify-content:flex-end;align-items:center;border-bottom:1px solid #dcdfe6">
        <span style="margin-right:12px">{{ auth.user?.username }}</span>
        <el-button size="small" @click="handleLogout">退出</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.logo {
  color: #fff;
  text-align: center;
  padding: 16px 0;
  font-size: 18px;
  font-weight: bold;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
</style>

<template>
  <!-- Login page: no sidebar -->
  <router-view v-if="route.path === '/login'" />

  <!-- Authenticated layout -->
  <el-container v-else class="app-container">
    <el-aside width="240px" class="app-sidebar">
      <div class="sidebar-header">
        <el-icon :size="24"><DataAnalysis /></el-icon>
        <span class="app-title">智能数据分析</span>
      </div>

      <!-- User & Workspace -->
      <div class="user-info">
        <div class="user-row">
          <el-icon><User /></el-icon>
          <span class="user-name">{{ auth.user?.display_name || auth.user?.username }}</span>
        </div>
        <div class="workspace-row" v-if="auth.workspace" @click="router.push('/team')" title="点击管理团队">
          <el-icon><OfficeBuilding /></el-icon>
          <span class="workspace-name">{{ auth.workspace.name }}</span>
          <el-tag size="small" :type="auth.workspace.role === 'admin' ? 'warning' : 'info'" class="role-tag">
            {{ auth.workspace.role === 'admin' ? '管理员' : '成员' }}
          </el-tag>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </el-menu-item>
        <el-menu-item index="/dashboard">
          <el-icon><TrendCharts /></el-icon>
          <span>数据看板</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <span>查询历史</span>
        </el-menu-item>
        <el-menu-item index="/team">
          <el-icon><Setting /></el-icon>
          <span>团队管理</span>
        </el-menu-item>
        <el-menu-item v-if="isAdmin()" index="/datasource">
          <el-icon><Coin /></el-icon>
          <span>数据源管理</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <el-button text size="small" @click="handleLogout" class="logout-btn">
          <el-icon><SwitchButton /></el-icon>
          退出登录
        </el-button>
        <p class="version-text">v3.0.0</p>
      </div>
    </el-aside>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth, isAdmin, logout } from './store/auth'

const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => route.path)

const handleLogout = () => {
  logout()
  router.push('/login')
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-container {
  height: 100vh;
}

.app-sidebar {
  background: #1a1a2e;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #16213e;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #e94560;
  border-bottom: 1px solid #16213e;
}

.app-title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

/* User info section */
.user-info {
  padding: 14px 20px;
  border-bottom: 1px solid #16213e;
}

.user-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ddd;
  font-size: 14px;
  margin-bottom: 6px;
}

.user-name {
  font-weight: 500;
}

.workspace-row {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  padding: 2px 4px;
  margin: 0 -4px;
  transition: background 0.2s;
}

.workspace-row:hover {
  background: rgba(255, 255, 255, 0.08);
}

.workspace-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-tag {
  flex-shrink: 0;
}

.sidebar-menu {
  flex: 1;
  background: transparent;
  border-right: none;
  padding-top: 10px;
}

.sidebar-menu .el-menu-item {
  color: #a8a8b3;
  margin: 4px 8px;
  border-radius: 8px;
}

.sidebar-menu .el-menu-item:hover {
  background: #16213e;
  color: #fff;
}

.sidebar-menu .el-menu-item.is-active {
  background: #0f3460;
  color: #e94560;
}

.sidebar-footer {
  padding: 12px 20px;
  text-align: center;
  border-top: 1px solid #16213e;
}

.logout-btn {
  color: #888 !important;
  font-size: 13px;
}

.logout-btn:hover {
  color: #e94560 !important;
}

.version-text {
  color: #555;
  font-size: 11px;
  margin-top: 6px;
}

.app-main {
  background: #f5f7fa;
  padding: 0;
  overflow: hidden;
}
</style>

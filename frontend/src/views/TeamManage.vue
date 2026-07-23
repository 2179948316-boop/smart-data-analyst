<template>
  <div class="team-page">
    <div class="page-header">
      <h2>团队管理</h2>
      <p class="subtitle">管理你的工作空间和团队成员</p>
    </div>

    <el-tabs v-model="activeTab" class="team-tabs">
      <!-- Tab 1: Members -->
      <el-tab-pane label="成员管理" name="members">
        <div class="tab-header">
          <h3>{{ auth.workspace?.name }} — 成员列表</h3>
          <el-button
            v-if="isAdmin()"
            type="primary"
            @click="inviteDialogVisible = true"
          >
            <el-icon><Plus /></el-icon>
            邀请成员
          </el-button>
        </div>

        <el-table :data="members" v-loading="membersLoading" stripe class="members-table">
          <el-table-column prop="username" label="用户名" width="160" />
          <el-table-column prop="display_name" label="显示名称" width="180" />
          <el-table-column prop="role" label="角色" width="120">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'warning' : 'info'" size="small">
                {{ row.role === 'admin' ? '管理员' : '成员' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="joined_at" label="加入时间">
            <template #default="{ row }">
              {{ row.joined_at ? new Date(row.joined_at).toLocaleDateString('zh-CN') : '-' }}
            </template>
          </el-table-column>
        </el-table>

        <p v-if="!membersLoading && members.length === 0" class="empty-text">暂无成员数据</p>
      </el-tab-pane>

      <!-- Tab 2: Workspaces -->
      <el-tab-pane label="工作空间" name="workspaces">
        <div class="tab-header">
          <h3>我的工作空间</h3>
          <el-button type="primary" @click="createDialogVisible = true">
            <el-icon><Plus /></el-icon>
            创建团队
          </el-button>
        </div>

        <div class="workspace-cards" v-loading="workspacesLoading">
          <div
            v-for="ws in workspaces"
            :key="ws.id"
            class="workspace-card"
            :class="{ active: ws.id === auth.workspace?.id }"
          >
            <div class="ws-info">
              <div class="ws-name">{{ ws.name }}</div>
              <div class="ws-meta">
                <el-tag size="small" :type="ws.role === 'admin' ? 'warning' : 'info'">
                  {{ ws.role === 'admin' ? '管理员' : '成员' }}
                </el-tag>
                <span class="ws-db">{{ ws.db_name }}</span>
              </div>
              <div v-if="ws.description" class="ws-desc">{{ ws.description }}</div>
            </div>
            <el-button
              v-if="ws.id !== auth.workspace?.id"
              size="small"
              @click="handleSwitchWorkspace(ws)"
            >
              切换
            </el-button>
            <el-tag v-else size="small" type="success">当前</el-tag>
          </div>
          <p v-if="!workspacesLoading && workspaces.length === 0" class="empty-text">暂无工作空间</p>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Invite Dialog -->
    <el-dialog v-model="inviteDialogVisible" title="邀请成员" width="420px" :close-on-click-modal="false">
      <el-form :model="inviteForm" label-width="80px" @submit.prevent="handleInvite">
        <el-form-item label="用户名">
          <el-input v-model="inviteForm.username" placeholder="输入要邀请的用户名" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="inviteForm.role">
            <el-radio value="member">成员（只读查询）</el-radio>
            <el-radio value="admin">管理员（可管理数据）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inviteDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="inviteLoading" @click="handleInvite">邀请</el-button>
      </template>
    </el-dialog>

    <!-- Create Workspace Dialog -->
    <el-dialog v-model="createDialogVisible" title="创建团队" width="420px" :close-on-click-modal="false">
      <el-form :model="createForm" label-width="80px" @submit.prevent="handleCreate">
        <el-form-item label="团队名称">
          <el-input v-model="createForm.name" placeholder="输入团队名称" maxlength="50" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="可选：描述这个团队的用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { auth, isAdmin, switchWorkspace } from '../store/auth'
import {
  listWorkspaces,
  createWorkspace,
  listMembers,
  inviteMember,
} from '../api'

const activeTab = ref('members')

// ── Members ──
const members = ref([])
const membersLoading = ref(false)

async function loadMembers() {
  if (!auth.workspace?.id) return
  membersLoading.value = true
  try {
    const res = await listMembers(auth.workspace.id)
    members.value = res.data.members || []
  } catch (e) {
    console.error('Failed to load members:', e)
  } finally {
    membersLoading.value = false
  }
}

// ── Invite ──
const inviteDialogVisible = ref(false)
const inviteLoading = ref(false)
const inviteForm = reactive({ username: '', role: 'member' })

async function handleInvite() {
  if (!inviteForm.username.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  inviteLoading.value = true
  try {
    await inviteMember(auth.workspace.id, {
      username: inviteForm.username.trim(),
      role: inviteForm.role,
    })
    ElMessage.success(`已邀请 ${inviteForm.username} 加入团队`)
    inviteForm.username = ''
    inviteForm.role = 'member'
    inviteDialogVisible.value = false
    loadMembers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '邀请失败')
  } finally {
    inviteLoading.value = false
  }
}

// ── Workspaces ──
const workspaces = ref([])
const workspacesLoading = ref(false)

async function loadWorkspaces() {
  workspacesLoading.value = true
  try {
    const res = await listWorkspaces()
    workspaces.value = res.data.workspaces || []
  } catch (e) {
    console.error('Failed to load workspaces:', e)
  } finally {
    workspacesLoading.value = false
  }
}

async function handleSwitchWorkspace(ws) {
  try {
    await switchWorkspace(ws.id)
    ElMessage.success(`已切换到「${ws.name}」`)
    // Reload data for new workspace
    loadMembers()
    loadWorkspaces()
  } catch (e) {
    ElMessage.error('切换失败')
  }
}

// ── Create Workspace ──
const createDialogVisible = ref(false)
const createLoading = ref(false)
const createForm = reactive({ name: '', description: '' })

async function handleCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入团队名称')
    return
  }
  createLoading.value = true
  try {
    await createWorkspace({
      name: createForm.name.trim(),
      description: createForm.description.trim() || undefined,
    })
    ElMessage.success(`团队「${createForm.name}」创建成功`)
    createForm.name = ''
    createForm.description = ''
    createDialogVisible.value = false
    loadWorkspaces()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    createLoading.value = false
  }
}

onMounted(() => {
  loadMembers()
  loadWorkspaces()
})
</script>

<style scoped>
.team-page {
  padding: 24px 32px;
  max-width: 900px;
  margin: 0 auto;
  height: 100%;
  overflow-y: auto;
}

.page-header h2 {
  font-size: 22px;
  font-weight: 600;
  color: #1a1a2e;
}

.subtitle {
  color: #888;
  font-size: 14px;
  margin-top: 4px;
}

.team-tabs {
  margin-top: 20px;
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.tab-header h3 {
  font-size: 16px;
  color: #333;
}

.members-table {
  border-radius: 8px;
  overflow: hidden;
}

.empty-text {
  color: #999;
  text-align: center;
  padding: 40px 0;
}

/* Workspace cards */
.workspace-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.workspace-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-radius: 10px;
  border: 1px solid #e8e8e8;
  background: #fff;
  transition: all 0.2s;
}

.workspace-card:hover {
  border-color: #c0c4cc;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.workspace-card.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.ws-info {
  flex: 1;
  min-width: 0;
}

.ws-name {
  font-size: 15px;
  font-weight: 500;
  color: #333;
}

.ws-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.ws-db {
  font-size: 12px;
  color: #999;
  font-family: monospace;
}

.ws-desc {
  font-size: 13px;
  color: #666;
  margin-top: 4px;
}
</style>

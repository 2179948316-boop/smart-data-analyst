import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, // 5 min for agent
})

// ── Token Interceptor ──
// Auto-attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = window.__auth_token__
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !window.location.pathname.includes('/login')) {
      window.__auth_token__ = null
      window.__auth_user__ = null
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ──
export const register = (data) => api.post('/auth/register', data)
export const login = (data) => api.post('/auth/login', data)
export const getMe = () => api.get('/auth/me')
export const selectWorkspace = (workspaceId) =>
  api.post('/auth/select-workspace', { workspace_id: workspaceId })

// ── Workspaces ──
export const listWorkspaces = () => api.get('/workspaces')
export const createWorkspace = (data) => api.post('/workspaces', data)
export const listMembers = (workspaceId) => api.get(`/workspaces/${workspaceId}/members`)
export const inviteMember = (workspaceId, data) =>
  api.post(`/workspaces/${workspaceId}/invite`, data)

// ── Chat / Query ──
export const askQuestion = (question, conversationId = null) =>
  api.post('/ask', { question, conversation_id: conversationId })

export const askQuestionStream = (question, conversationId = null) => {
  const token = window.__auth_token__
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  return fetch('/api/ask/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify({ question, conversation_id: conversationId }),
  })
}

// ── Conversations ──
export const listConversations = () => api.get('/conversations')
export const createConversation = (title = '新对话') => api.post('/conversations', { title })
export const getConversation = (id) => api.get(`/conversations/${id}`)
export const deleteConversation = (id) => api.delete(`/conversations/${id}`)

// ── History ──
export const getHistory = (page = 1, pageSize = 20) =>
  api.get('/history', { params: { page, page_size: pageSize } })

// ── Data Sources ──
export const listDataSources = () => api.get('/datasources')
export const createDataSource = (data) => api.post('/datasources', data)
export const uploadFile = (file, tableName = '', ifExists = 'rename') => {
  const form = new FormData()
  form.append('file', file)
  if (tableName) form.append('table_name', tableName)
  form.append('if_exists', ifExists)
  return api.post('/datasources/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 min for large files
  })
}
export const listTables = () => api.get('/datasources/tables')
export const deleteTable = (tableName) => api.delete(`/datasources/tables/${tableName}`)

// ── Chart / SQL Execution ──
export const executeSql = (sql) => api.post('/execute-sql', { sql })

// ── SQL Write Preview & Confirm ──
export const sqlPreview = (sql) => api.post('/sql/preview', { sql })
export const sqlConfirm = (sql) => api.post('/sql/confirm', { sql })

// ── SQL EXPLAIN ──
export const sqlExplain = (sql) => api.post('/sql/explain', { sql })

// ── Performance Stats ──
export const getPerformanceStats = (limit = 50) =>
  api.get('/performance/stats', { params: { limit } })

// ── Dashboard ──
export const getDashboardStats = () => api.get('/dashboard/stats')
export const getDashboardModule = (key) => api.get(`/dashboard/stats/${key}`)

// ── Health ──
export const healthCheck = () => api.get('/health')

export default api

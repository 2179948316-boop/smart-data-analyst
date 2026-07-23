/**
 * Auth store — simple global reactive state for authentication.
 * Uses window.__auth_token__ for persistence and axios interceptor integration.
 */
import { reactive } from 'vue'
import { login as apiLogin, register as apiRegister, selectWorkspace as apiSelectWorkspace } from '../api'

export const auth = reactive({
  user: null,
  workspace: null,
  token: null,
  isLoggedIn: false,
})

// Restore from sessionStorage on load
function restore() {
  const token = sessionStorage.getItem('token')
  const user = sessionStorage.getItem('user')
  const workspace = sessionStorage.getItem('workspace')
  if (token) {
    auth.token = token
    auth.user = user ? JSON.parse(user) : null
    auth.workspace = workspace ? JSON.parse(workspace) : null
    auth.isLoggedIn = true
    window.__auth_token__ = token
    window.__auth_user__ = auth.user
  }
}

function persist(token, user, workspace) {
  auth.token = token
  auth.user = user
  auth.workspace = workspace
  auth.isLoggedIn = true
  window.__auth_token__ = token
  window.__auth_user__ = user
  sessionStorage.setItem('token', token)
  sessionStorage.setItem('user', JSON.stringify(user))
  if (workspace) {
    sessionStorage.setItem('workspace', JSON.stringify(workspace))
  }
}

export function logout() {
  auth.token = null
  auth.user = null
  auth.workspace = null
  auth.isLoggedIn = false
  window.__auth_token__ = null
  window.__auth_user__ = null
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('user')
  sessionStorage.removeItem('workspace')
}

export async function login(username, password) {
  const res = await apiLogin({ username, password })
  const { access_token, user, workspace } = res.data
  persist(access_token, user, workspace)
  return res.data
}

export async function registerUser(username, email, password, displayName) {
  const res = await apiRegister({
    username,
    email,
    password,
    display_name: displayName || undefined,
  })
  const { access_token, user, workspace } = res.data
  persist(access_token, user, workspace)
  return res.data
}

export async function switchWorkspace(workspaceId) {
  const res = await apiSelectWorkspace(workspaceId)
  const { access_token, workspace } = res.data
  auth.token = access_token
  auth.workspace = workspace
  window.__auth_token__ = access_token
  sessionStorage.setItem('token', access_token)
  sessionStorage.setItem('workspace', JSON.stringify(workspace))
  return res.data
}

// Check role
export function isAdmin() {
  return auth.workspace?.role === 'admin'
}

export function isMember() {
  return auth.workspace?.role === 'member'
}

// Auto-restore on module load
restore()

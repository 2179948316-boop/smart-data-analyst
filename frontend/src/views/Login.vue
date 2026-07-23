<template>
  <div class="login-page">
    <div class="login-card">
      <div class="logo">
        <h1>智能数据分析助手</h1>
        <p>用自然语言提问，AI 帮你分析数据</p>
      </div>

      <el-tabs v-model="activeTab" stretch>
        <el-tab-pane label="登录" name="login">
          <el-form ref="loginForm" :model="loginData" :rules="loginRules" @submit.prevent="handleLogin">
            <el-form-item prop="username">
              <el-input
                v-model="loginData.username"
                placeholder="用户名"
                prefix-icon="User"
                size="large"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="loginData.password"
                type="password"
                placeholder="密码"
                prefix-icon="Lock"
                size="large"
                show-password
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                style="width: 100%"
                :loading="loading"
                @click="handleLogin"
              >
                登录
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form ref="registerForm" :model="registerData" :rules="registerRules" @submit.prevent="handleRegister">
            <el-form-item prop="username">
              <el-input
                v-model="registerData.username"
                placeholder="用户名（2-50 位）"
                prefix-icon="User"
                size="large"
              />
            </el-form-item>
            <el-form-item prop="email">
              <el-input
                v-model="registerData.email"
                placeholder="邮箱"
                prefix-icon="Message"
                size="large"
              />
            </el-form-item>
            <el-form-item prop="displayName">
              <el-input
                v-model="registerData.displayName"
                placeholder="显示名称（可选）"
                prefix-icon="Postcard"
                size="large"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="registerData.password"
                type="password"
                placeholder="密码（至少 6 位）"
                prefix-icon="Lock"
                size="large"
                show-password
              />
            </el-form-item>
            <el-form-item prop="confirmPassword">
              <el-input
                v-model="registerData.confirmPassword"
                type="password"
                placeholder="确认密码"
                prefix-icon="Lock"
                size="large"
                show-password
                @keyup.enter="handleRegister"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                style="width: 100%"
                :loading="loading"
                @click="handleRegister"
              >
                注册
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, registerUser } from '../store/auth'

const router = useRouter()
const activeTab = ref('login')
const loading = ref(false)

// Login
const loginForm = ref(null)
const loginData = reactive({ username: '', password: '' })
const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const handleLogin = async () => {
  const valid = await loginForm.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await login(loginData.username, loginData.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

// Register
const registerForm = ref(null)
const registerData = reactive({
  username: '', email: '', displayName: '', password: '', confirmPassword: '',
})
const validateConfirm = (rule, value, callback) => {
  if (value !== registerData.password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}
const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '长度 2-50 位', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

const handleRegister = async () => {
  const valid = await registerForm.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await registerUser(
      registerData.username,
      registerData.email,
      registerData.password,
      registerData.displayName,
    )
    ElMessage.success('注册成功，已自动创建团队')
    router.push('/')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 420px;
  background: #fff;
  border-radius: 16px;
  padding: 40px 36px 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.logo {
  text-align: center;
  margin-bottom: 28px;
}

.logo h1 {
  margin: 0;
  font-size: 22px;
  color: #333;
}

.logo p {
  margin: 8px 0 0;
  font-size: 13px;
  color: #999;
}
</style>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>

      <h1>登录工作台</h1>

      <form class="form" @submit.prevent="submit">
        <label>
          <span>邮箱</span>
          <input v-model.trim="email" type="email" autocomplete="username" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>

        <p v-if="message" class="error">{{ message }}</p>

        <button type="submit" :disabled="loading">
          {{ loading ? '正在登录…' : '进入工作台' }}
        </button>
      </form>

      <p class="hint">
        客户：client@demo.local / demo1234<br />
        项目经理：pm@demo.local / demo1234<br />
        律师 / 管理员：lawyer@demo.local / admin@demo.local<br />
        服务商 / 专家：provider@demo.local / expert@demo.local，密码同上
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('pm@demo.local')
const password = ref('demo1234')
const loading = ref(false)
const message = ref('')

async function submit() {
  message.value = ''
  if (!email.value || !password.value) {
    message.value = '请输入邮箱和密码。'
    return
  }
  loading.value = true
  try {
    const user = await auth.login(email.value, password.value)
    if (user.role === 'provider') {
      router.push('/provider')
    } else if (user.role === 'expert') {
      router.push('/expert')
    } else {
      router.push('/')
    }
  } catch (error) {
    message.value =
      error.response?.data?.message || '登录失败，请检查账号或后端服务。'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(900px 420px at 50% -10%, rgba(77, 107, 254, 0.1), transparent 65%),
    var(--bg);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 380px;
  padding: 36px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 36px;
}

.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: #fff;
  background: var(--accent);
  font-weight: 700;
  font-size: 14px;
}

.brand-name {
  font-weight: 650;
}

h1 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.02em;
}

.sub {
  margin: 8px 0 28px;
  color: var(--text-2);
  font-size: 13px;
}

.form {
  display: grid;
  gap: 16px;
}

label {
  display: grid;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
}

input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fff;
  color: var(--text);
  outline: none;
}

input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(77, 107, 254, 0.12);
}

button {
  height: 42px;
  border: 0;
  border-radius: 9px;
  background: var(--accent);
  color: #fff;
  font-weight: 650;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: default;
}

.error {
  margin: 0;
  color: #dc2626;
  font-size: 12px;
}

.hint {
  margin: 24px 0 0;
  font-size: 12px;
  color: var(--text-3);
  text-align: center;
}
</style>

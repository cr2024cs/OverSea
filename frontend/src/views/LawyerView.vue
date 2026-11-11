<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span>复核律师工作台</span>
      </div>
      <div class="user">
        <span>{{ auth.user?.name }}</span>
        <button @click="logout">退出</button>
      </div>
    </header>

    <main class="content">
      <div v-if="loading" class="state">正在加载…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>
      <template v-else-if="data">
        <h1>待审批质询函</h1>
        <div v-if="!data.pending_letters.length" class="state">暂无待审批质询。</div>
        <article v-for="letter in data.pending_letters" :key="letter.id" class="card">
          <div class="card-head">
            <strong>{{ letter.project_name }}</strong>
            <span class="tag">{{ letter.status }}</span>
          </div>
          <pre class="content-box">{{ letter.content }}</pre>
          <div class="actions">
            <button class="primary" @click="approve(letter)">批准</button>
            <button class="ghost" @click="reject(letter)">驳回（误报）</button>
          </div>
        </article>

        <h1>项目</h1>
        <div class="grid">
          <article
            v-for="project in data.projects"
            :key="project.id"
            class="project"
            @click="openProject(project)"
          >
            <strong>{{ project.name }}</strong>
            <span>{{ project.client_name }}</span>
            <span class="muted">阶段 {{ project.phase }}/7 · {{ project.status }}</span>
          </article>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(true)
const error = ref('')
const data = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.get('/lawyer/workbench')
    data.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function approve(letter) {
  try {
    await client.post(`/query-letters/${letter.id}/approve`)
    ElMessage.success('已批准')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '操作失败')
  }
}

async function reject(letter) {
  try {
    const { value } = await ElMessageBox.prompt('请填写驳回原因', '驳回质询', {
      inputValidator: (input) => Boolean(input?.trim()) || '原因不能为空'
    })
    await client.post(`/query-letters/${letter.id}/reject`, { reason: value })
    ElMessage.success('已驳回')
    await load()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.message || '操作失败')
    }
  }
}

function openProject(project) {
  router.push(`/projects/${project.id}`)
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(load)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: var(--bg);
}

.topbar {
  height: 60px;
  padding: 0 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  background: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 650;
}

.brand-mark {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
}

.user {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-2);
}

.user button {
  border: 0;
  background: none;
  color: var(--text-3);
  cursor: pointer;
}

.content {
  max-width: 900px;
  margin: 0 auto;
  padding: 30px 24px 60px;
}

h1 {
  margin: 0 0 12px;
  font-size: 20px;
}

.card {
  margin-bottom: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
}

.card-head {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.tag {
  padding: 1px 8px;
  border-radius: 999px;
  background: #fff7e6;
  color: #b45309;
  font-size: 11px;
}

.content-box {
  max-height: 200px;
  overflow: auto;
  padding: 10px;
  border-radius: 8px;
  background: #fafbfc;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.primary,
.ghost {
  height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}

.primary {
  border: 0;
  background: var(--accent);
  color: #fff;
}

.ghost {
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text-2);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}

.project {
  display: grid;
  gap: 4px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
}

.muted {
  color: var(--text-3);
  font-size: 11px;
}

.state {
  padding: 30px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}

.state.error {
  color: #dc2626;
}

@media (max-width: 720px) {
  .topbar {
    padding: 0 16px;
  }

  .content {
    padding: 22px 14px 40px;
  }
}
</style>

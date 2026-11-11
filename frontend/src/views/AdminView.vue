<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span>管理员控制台</span>
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
        <div class="actions">
          <button class="primary" @click="exportMetrics">导出指标 JSON</button>
          <button class="ghost" @click="resetDemo">一键重置演示数据</button>
        </div>

        <div class="counts">
          <div v-for="(value, key) in data.counts" :key="key" class="count">
            <strong>{{ value }}</strong>
            <span>{{ countLabel(key) }}</span>
          </div>
        </div>

        <h2>账号</h2>
        <div class="table">
          <div class="row head">
            <span>邮箱</span><span>姓名</span><span>公司</span><span>角色</span>
          </div>
          <div v-for="user in data.users" :key="user.email" class="row">
            <span>{{ user.email }}</span>
            <span>{{ user.name }}</span>
            <span>{{ user.company || '—' }}</span>
            <span>{{ roleLabel(user.role) }}</span>
          </div>
        </div>

        <h2>最近审计</h2>
        <div class="audits">
          <div v-for="log in data.audit_logs" :key="log.id" class="audit">
            <span class="action">{{ log.action }}</span>
            <span>{{ log.actor || 'system' }}</span>
            <span class="muted">{{ log.created_at }}</span>
          </div>
          <div v-if="!data.audit_logs.length" class="state">暂无日志。</div>
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

function roleLabel(value) {
  return (
    {
      client: '客户',
      pm: '项目经理',
      lawyer: '复核律师',
      admin: '管理员',
      provider: '服务商',
      expert: '验收专家'
    }[value] || value
  )
}

function countLabel(key) {
  return (
    {
      users: '账号',
      projects: '项目',
      providers: '服务商',
      task_templates: '任务模板',
      tasks: '任务',
      contracts: '合同',
      milestones: '节点',
      archives: '归档'
    }[key] || key
  )
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.get('/admin/overview')
    data.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function exportMetrics() {
  try {
    const response = await client.get('/metrics/export', {
      responseType: 'blob'
    })
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'metrics.json'
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '导出失败')
  }
}

async function resetDemo() {
  try {
    await ElMessageBox.confirm('将清空并重建演示项目，是否继续？', '一键重置', {
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await client.post('/admin/demo/reset')
    ElMessage.success('演示数据已重置')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '重置失败')
  }
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
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px 24px 60px;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.primary,
.ghost {
  height: 34px;
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

.counts {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  margin: 24px 0 30px;
}

.count {
  display: grid;
  gap: 4px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
}

.count strong {
  font-size: 22px;
}

.count span {
  font-size: 11px;
  color: var(--text-3);
}

h2 {
  margin: 28px 0 10px;
  font-size: 15px;
}

.table {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}

.row {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr 1fr 0.6fr;
  gap: 10px;
  padding: 10px 12px;
  border-top: 1px solid #f1f2f4;
  font-size: 12px;
}

.row.head {
  border-top: 0;
  background: #fafbfc;
  color: var(--text-3);
  font-size: 11px;
}

.audits {
  display: grid;
  gap: 6px;
}

.audit {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  font-size: 11px;
}

.action {
  color: var(--accent);
  font-weight: 600;
}

.muted {
  color: var(--text-3);
}

.state {
  padding: 40px 0;
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

  .row {
    grid-template-columns: 1.4fr 1fr;
  }

  .row span:nth-child(3),
  .row span:nth-child(4) {
    display: none;
  }

  .row.head span:nth-child(3),
  .row.head span:nth-child(4) {
    display: none;
  }
}
</style>

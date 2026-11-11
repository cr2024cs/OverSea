<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>
      <div class="top-actions">
        <button
          v-if="['client', 'pm', 'admin'].includes(auth.user?.role)"
          class="primary small"
          @click="showCreate = true"
        >
          + 新建项目
        </button>
        <div class="user">
          <span>{{ auth.user?.name }}</span>
          <span class="role">{{ roleLabel(auth.user?.role) }}</span>
          <button class="link" @click="logout">退出</button>
        </div>
      </div>
    </header>

    <main class="content">
      <div class="heading">
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>
      </div>

      <div v-if="loading" class="state">正在加载项目…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>
      <div v-else-if="!projects.length" class="empty">
        <h2>还没有项目</h2>
        <p>点击右上角“新建项目”开始。</p>
      </div>

      <div v-else class="grid">
        <article
          v-for="project in projects"
          :key="project.id"
          class="card"
          @click="openProject(project)"
        >
          <div class="card-top">
            <span class="name">{{ project.name }}</span>
            <span class="status">{{ statusLabel(project.status) }}</span>
          </div>
          <p class="client">{{ project.client_name }}</p>
          <div class="steps">
            <span
              v-for="index in 7"
              :key="index"
              class="dot"
              :class="{ active: index <= project.phase, current: index === project.phase }"
            ></span>
          </div>
          <div class="meta">
            <span>阶段 {{ project.phase }}/7</span>
            <span>{{ investment(project) }}</span>
          </div>
        </article>
      </div>
    </main>

    <CreateProjectDialog v-model="showCreate" @created="openProject" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import client from '../api/client'
import CreateProjectDialog from '../components/CreateProjectDialog.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const projects = ref([])
const loading = ref(true)
const error = ref('')
const showCreate = ref(false)

const title = computed(() => {
  if (auth.user?.role === 'client') return '我的项目'
  if (auth.user?.role === 'pm') return '项目列表'
  return '全部项目'
})

const subtitle = computed(() => {
  if (auth.user?.role === 'client') return '创建项目并跟踪诊断、建议书、报价、合同与验收进度。'
  if (auth.user?.role === 'pm') return '查看全部客户项目，进入工作台推进七阶段。'
  return '查看项目与阶段进度。'
})

function roleLabel(value) {
  return (
    { client: '客户', pm: '项目经理', lawyer: '复核律师', admin: '管理员' }[value] ||
    value
  )
}

function statusLabel(value) {
  return (
    {
      draft: '新建',
      diagnosing: '调研中',
      requirement_pending: '需求待确认',
      proposal_pending: '建议书待确认',
      service_selecting: '服务选择中',
      inquiry_sent: '询价中',
      quote_pending: '报价待确认',
      quote_confirmed: '报价已确认',
      contracting: '签约中',
      active: '已生效',
      executing: '执行中',
      accepting: '验收中',
      closed: '已关闭',
      paused: '已暂停',
      cancelled: '已取消'
    }[value] || value
  )
}

function investment(project) {
  if (!project.investment_cents) return '投资待定'
  const amount = Number(project.investment_cents) / 100
  const formatted = amount.toLocaleString('zh-CN', {
    maximumFractionDigits: 0
  })
  return `${project.currency || ''} ${formatted}`
}

function openProject(project) {
  router.push(`/projects/${project.id}`)
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  try {
    const response = await client.get('/projects')
    projects.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '项目加载失败'
  } finally {
    loading.value = false
  }
})
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
  font-weight: 700;
}

.brand-name {
  font-weight: 650;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-2);
}

.role {
  padding: 1px 7px;
  border-radius: 999px;
  background: #eef1ff;
  color: var(--accent);
  font-size: 10px;
}

.link {
  border: 0;
  background: none;
  color: var(--text-3);
  font-size: 11px;
  cursor: pointer;
}

.primary {
  height: 32px;
  padding: 0 16px;
  border: 0;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

.small {
  height: 30px;
}

.content {
  max-width: 1180px;
  margin: 0 auto;
  padding: 36px 40px 60px;
}

.heading h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: -0.02em;
}

.heading p {
  margin: 8px 0 28px;
  color: var(--text-2);
  font-size: 13px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.card {
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  transition: 0.15s ease;
}

.card:hover {
  border-color: #c9d1ff;
  transform: translateY(-1px);
}

.card-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.name {
  font-weight: 650;
  font-size: 14px;
  line-height: 1.5;
}

.status {
  flex: none;
  padding: 1px 7px;
  border-radius: 999px;
  background: #f3f4f6;
  color: var(--text-2);
  font-size: 10px;
  height: 20px;
  display: inline-flex;
  align-items: center;
}

.client {
  margin: 6px 0 14px;
  font-size: 12px;
  color: var(--text-3);
}

.steps {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
}

.dot {
  flex: 1;
  height: 4px;
  border-radius: 999px;
  background: #eef0f3;
}

.dot.active {
  background: #c9d1ff;
}

.dot.current {
  background: var(--accent);
}

.meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-3);
}

.state {
  padding: 48px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}

.state.error {
  color: #dc2626;
}

.empty {
  padding: 60px 20px;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: 12px;
  background: #fff;
}

.empty h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

.empty p {
  margin: 0;
  color: var(--text-3);
  font-size: 13px;
}

@media (max-width: 720px) {
  .topbar {
    padding: 0 16px;
    height: 56px;
  }

  .content {
    padding: 24px 16px 40px;
  }

  .heading h1 {
    font-size: 22px;
  }

  .top-actions {
    gap: 8px;
  }

  .user span:first-child {
    display: none;
  }

  .role {
    display: none;
  }
}
</style>

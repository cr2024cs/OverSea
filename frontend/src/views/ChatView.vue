<template>
  <div class="shell">
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="brand-row">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
        <button class="sidebar-close" @click="sidebarOpen = false">关闭</button>
      </div>

      <div class="side-scroll">
        <button class="back-home" @click="router.push('/')">← 全部项目</button>
        <div class="side-label row">
          <span>项目</span>
          <button
            v-if="['client', 'pm', 'admin'].includes(auth.user?.role)"
            class="new-conv"
            @click="showCreate = true"
          >
            +
          </button>
        </div>
        <button
          v-for="project in projects"
          :key="project.id"
          class="project-item"
          :class="{ active: project.id === selectedProjectId }"
          @click="selectProject(project.id)"
        >
          <span class="project-name">{{ project.name }}</span>
          <span class="project-meta">
            阶段 {{ project.phase }} · {{ statusLabel(project.status) }}
          </span>
        </button>
        <div v-if="!projects.length" class="side-empty">暂无项目</div>
      </div>

      <div class="user-box">
        <span class="avatar small">{{ auth.user?.name?.slice(0, 1) || 'U' }}</span>
        <div class="user-meta">
          <strong>{{ auth.user?.name || '未登录' }}</strong>
          <span>{{ roleLabel(auth.user?.role) }}</span>
        </div>
        <button class="logout" @click="logout">退出</button>
      </div>
    </aside>

    <main class="main">
      <header class="chat-header">
        <div class="title-row">
          <button class="mobile-menu" @click="sidebarOpen = true">菜单</button>
          <h2>{{ selectedProject?.name || '选择项目' }}</h2>
          <span v-if="selectedProject" class="status-pill">
            {{ statusLabel(selectedProject.status) }}
          </span>
          <button class="panel-toggle" @click="panelOpen = true">工作台</button>
        </div>
        <div class="steps">
          <div
            v-for="(step, index) in phaseSteps"
            :key="step"
            class="step"
            :class="{ active: index + 1 === phase, done: index + 1 < phase }"
          >
            <span class="dot">{{ index + 1 }}</span>
            <span class="step-label">{{ step }}</span>
          </div>
        </div>
      </header>

      <div v-if="nextStep" class="phase-guide">
        <span class="guide-label">下一步</span>
        <span class="guide-text">{{ nextStep.text }}</span>
        <button
          v-if="nextStep.action"
          class="guide-action"
          :disabled="guideBusy"
          @click="runNextStep"
        >
          {{ guideBusy ? '处理中…' : nextStep.actionLabel }}
        </button>
      </div>

      <div ref="messageListRef" class="messages">
        <div v-if="loading" class="empty">正在载入项目…</div>

        <div v-else-if="!messages.length" class="empty-state">
          <h3>从一个目标开始</h3>
          <p>
            描述你的出海计划，或上传资料。系统会先整理事实与追问，再生成任务地图与建议书。
          </p>
          <div class="suggestions">
            <button
              v-for="suggestion in suggestions"
              :key="suggestion.label"
              @click="sendMessage(suggestion.text)"
            >
              {{ suggestion.label }}
            </button>
          </div>
        </div>

        <div
          v-for="message in messages"
          :key="message.id"
          class="message"
          :class="message.role"
        >
          <div v-if="message.role === 'assistant'" class="avatar">AI</div>
          <div class="message-body">
            <div v-if="message.role === 'user'" class="user-bubble">
              {{ message.content }}
            </div>
            <template v-else>
              <div class="markdown" v-html="renderMarkdown(message.content)"></div>
              <span v-if="message.streaming" class="cursor"></span>
              <div v-if="message.error" class="message-meta">
                <span class="failed">请求失败</span>
              </div>
            </template>
          </div>
        </div>
      </div>

      <div class="composer">
        <div class="input-box">
          <button class="attach" :disabled="uploading" @click="fileInput?.click()">
            {{ uploading ? '上传中' : '附件' }}
          </button>
          <input
            ref="fileInput"
            class="hidden-file"
            type="file"
            accept=".txt,.md,.docx,.pdf"
            @change="handleFile"
          />
          <textarea
            v-model="input"
            rows="1"
            placeholder="描述目标，Enter 发送，Shift + Enter 换行"
            @keydown.enter.exact="handleEnter"
          ></textarea>
          <button class="send" :disabled="sending || !input.trim()" @click="sendMessage()">
            {{ sending ? '生成中' : '发送' }}
          </button>
        </div>
        <p class="disclaimer">AI 生成内容需人工确认后才能对外发送。</p>
      </div>
    </main>

    <div v-if="panelOpen" class="panel-backdrop" @click="panelOpen = false"></div>
    <ArtifactPanel
      ref="artifactPanelRef"
      class="panel wide"
      :class="{ open: panelOpen }"
      :project-id="selectedProjectId"
      :refresh-token="artifactRefresh"
      :phase="phase"
      @refresh-project="refreshSelectedProject"
      @demo-reset="reloadAfterReset"
    />
    <button v-if="panelOpen" class="panel-close" @click="panelOpen = false">
      关闭
    </button>

    <CreateProjectDialog
      v-model="showCreate"
      @created="handleProjectCreated"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import ArtifactPanel from '../components/ArtifactPanel.vue'
import CreateProjectDialog from '../components/CreateProjectDialog.vue'
import { useAuthStore } from '../stores/auth'
import { renderMarkdown } from '../utils/markdown'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const projects = ref([])
const conversations = ref([])
const messages = ref([])
const selectedProjectId = ref('')
const conversationId = ref('')
const input = ref('')
const loading = ref(true)
const showCreate = ref(false)
const sidebarOpen = ref(false)
const panelOpen = ref(false)
const sending = ref(false)
const uploading = ref(false)
const artifactRefresh = ref(0)
const messageListRef = ref(null)
const fileInput = ref(null)
const artifactPanelRef = ref(null)
const guideBusy = ref(false)

const phaseSteps = ['调研', '建议', '询价', '报价', '签约', '履约', '归档']
const suggestions = [
  { label: '描述建厂目标', text: '我们计划在泰国设厂，投资约 3000 万美元，目标 14 个月试产。' },
  { label: '列出待确认问题', text: '请根据现有资料，列出还需要客户确认的关键问题。' },
  { label: '询问主要合规风险', text: '这个泰国设厂项目最关键的合规风险有哪些？' }
]

const selectedProject = computed(() =>
  projects.value.find((project) => project.id === selectedProjectId.value)
)
const phase = computed(() => selectedProject.value?.phase || 1)

const nextStep = computed(() => {
  const project = selectedProject.value
  if (!project) return null
  if (project.archived || project.phase === 7) {
    return { text: '项目已归档，当前为只读状态。', action: '', actionLabel: '' }
  }

  const role = auth.user?.role
  if (project.phase === 1) {
    if (role === 'client') {
      return {
        text: '问卷已完成。等待 PM 完成调研后，建议书会进入你的“客户确认”。',
        action: '',
        actionLabel: ''
      }
    }
    if (project.status === 'draft') {
      return {
        text: '调研尚未开始，先生成任务地图。',
        action: 'tasks',
        actionLabel: '生成任务地图',
        generate: true
      }
    }
    if (project.status === 'diagnosing') {
      return {
        text: '任务地图已生成，下一步生成需求确认书。',
        action: 'requirement',
        actionLabel: '生成需求确认书',
        generate: true
      }
    }
    return {
      text: '阶段 1 已完成，下一步生成正式项目建议书。',
      action: 'proposal',
      actionLabel: '生成项目建议书',
      generate: true
    }
  }
  if (project.phase === 2) {
    return role === 'client'
      ? { text: '建议书待你确认。', action: 'client-portal', actionLabel: '去确认' }
      : { text: '建议书待审核并发送客户。', action: 'proposal', actionLabel: '打开建议书' }
  }
  if (project.phase === 3) {
    return {
      text: '进入询价阶段。',
      action: 'selection',
      actionLabel: '打开选服务'
    }
  }
  if (project.phase === 4) {
    return role === 'client'
      ? { text: '总报价待你确认。', action: 'client-portal', actionLabel: '去确认' }
      : { text: '完成比价并生成客户总报价。', action: 'quotes', actionLabel: '打开报价' }
  }
  if (project.phase === 5) {
    return role === 'client'
      ? { text: '合同待你确认。', action: 'client-portal', actionLabel: '去确认' }
      : { text: '完成合同复核与双方确认。', action: 'contract', actionLabel: '打开合同' }
  }
  if (project.phase === 6) {
    if (role === 'client') {
      return {
        text: '节点待你确认。',
        action: 'client-portal',
        actionLabel: '去确认'
      }
    }
    if (role === 'lawyer') {
      return {
        text: '查看审查发现与待审批质询。',
        action: 'review',
        actionLabel: '打开审查'
      }
    }
    return {
      text: '推进履约、审查与节点验收。',
      action: 'milestones',
      actionLabel: '打开节点'
    }
  }
  return null
})

function statusLabel(value) {
  return (
    {
      draft: '新建',
      diagnosing: '调研中',
      requirement_pending: '需求待确认',
      proposal_generating: '建议书生成中',
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

function roleLabel(value) {
  return (
    { client: '客户', pm: '项目经理', lawyer: '复核律师', admin: '管理员' }[value] ||
    value
  )
}

function scrollToBottom() {
  nextTick(() => {
    const element = messageListRef.value
    if (element) element.scrollTop = element.scrollHeight
  })
}

async function selectConversation(id) {
  conversationId.value = id
  sidebarOpen.value = false
  const response = await client.get(`/conversations/${id}/messages`)
  messages.value = response.data.data
  loading.value = false
  scrollToBottom()
}

async function newConversation() {
  if (!selectedProjectId.value) return
  sidebarOpen.value = false
  const response = await client.post(
    `/projects/${selectedProjectId.value}/conversations`,
    {}
  )
  const conversation = response.data.data
  conversations.value.unshift({
    id: conversation.id,
    title: conversation.title
  })
  conversationId.value = conversation.id
  messages.value = []
}

async function loadProject(id) {
  if (!id) return
  selectedProjectId.value = id
  conversationId.value = ''
  messages.value = []
  loading.value = true
  try {
    const response = await client.get(`/projects/${id}/conversations`)
    conversations.value = response.data.data
    if (!conversations.value.length) {
      await newConversation()
      loading.value = false
    } else {
      await selectConversation(conversations.value[0].id)
    }
  } catch (error) {
    loading.value = false
    messages.value = [
      {
        id: 'load-error',
        role: 'assistant',
        content: `项目载入失败：${error.response?.data?.message || error.message}`,
        error: true
      }
    ]
  }
}

function selectProject(id) {
  if (!id) return
  sidebarOpen.value = false
  if (route.params.projectId !== id) {
    router.push({ name: 'chat', params: { projectId: id } })
    return
  }
  loadProject(id)
}

watch(
  () => route.params.projectId,
  (id) => {
    if (id) loadProject(id)
  }
)

async function refreshConversations() {
  if (!selectedProjectId.value) return
  const response = await client.get(
    `/projects/${selectedProjectId.value}/conversations`
  )
  conversations.value = response.data.data
}

async function sendMessage(textOverride) {
  const text = String(textOverride ?? input.value).trim()
  if (!text || sending.value || !conversationId.value) return

  input.value = ''
  messages.value.push({
    id: `local-user-${Date.now()}`,
    role: 'user',
    content: text
  })
  const assistant = {
    id: `local-assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    streaming: true,
    model: ''
  }
  messages.value.push(assistant)
  sending.value = true
  scrollToBottom()

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${auth.token}`
      },
      body: JSON.stringify({
        conversation_id: conversationId.value,
        message: text
      })
    })

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      throw new Error(payload.message || '请求失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        for (const line of block.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = JSON.parse(line.slice(5).trim())
          if (payload.delta) {
            assistant.content += payload.delta
            scrollToBottom()
          }
          if (payload.done) {
            assistant.id = payload.message_id || assistant.id
            assistant.model = payload.model
            assistant.streaming = false
          }
        }
        boundary = buffer.indexOf('\n\n')
      }
    }

    if (assistant.streaming) assistant.streaming = false
    artifactRefresh.value += 1
    await refreshConversations()
  } catch (error) {
    assistant.content = `请求失败：${error.message}`
    assistant.streaming = false
    assistant.error = true
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

async function refreshSelectedProject() {
  if (!selectedProjectId.value) return
  try {
    const response = await client.get(`/projects/${selectedProjectId.value}`)
    const updated = response.data.data
    const index = projects.value.findIndex((item) => item.id === updated.id)
    if (index >= 0) {
      projects.value[index] = updated
    }
  } catch {
    /* 刷新失败时保留本地状态 */
  }
}

watch(panelOpen, (open) => {
  if (open) refreshSelectedProject()
})

function handleWindowFocus() {
  refreshSelectedProject()
}

onMounted(() => window.addEventListener('focus', handleWindowFocus))
onBeforeUnmount(() => window.removeEventListener('focus', handleWindowFocus))

async function runNextStep() {
  const step = nextStep.value
  if (!step?.action || guideBusy.value) return

  guideBusy.value = true
  try {
    if (step.generate) {
      if (step.action === 'tasks') {
        await client.post(
          `/projects/${selectedProjectId.value}/tasks/refresh`,
          { scenario: 'lease' }
        )
      } else if (step.action === 'requirement') {
        await client.post(`/projects/${selectedProjectId.value}/requirement`)
      } else if (step.action === 'proposal') {
        await client.post(`/projects/${selectedProjectId.value}/proposals`)
      }
      await refreshSelectedProject()
      artifactRefresh.value += 1
    }

    artifactPanelRef.value?.setTab(step.action)
    panelOpen.value = true
    ElMessage.success(step.generate ? '已生成，可在工作台查看' : '已打开对应页面')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '操作失败')
  } finally {
    guideBusy.value = false
  }
}

function logout() {
  auth.logout()
  router.push('/login')
}

function handleEnter(event) {
  if (event.isComposing) return
  event.preventDefault()
  sendMessage()
}

function reloadAfterReset() {
  router.push('/')
}

async function handleProjectCreated(project) {
  projects.value = [project, ...projects.value]
  await router.push({ name: 'chat', params: { projectId: project.id } })
}

async function handleFile(event) {
  const file = event.target.files?.[0]
  if (!file || !selectedProjectId.value) return

  uploading.value = true
  const form = new FormData()
  form.append('file', file)
  try {
    await client.post(
      `/projects/${selectedProjectId.value}/documents`,
      form
    )
    ElMessage.success(`已上传 ${file.name}`)
    artifactRefresh.value += 1
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '上传失败')
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}

onMounted(async () => {
  try {
    const me = await client.get('/auth/me')
    auth.user = me.data.data
  } catch {
    auth.logout()
    router.push('/login')
    return
  }

  try {
    const response = await client.get('/projects')
    projects.value = response.data.data
    const projectId = route.params.projectId
    if (!projectId) {
      await router.replace('/')
      return
    }
    await loadProject(projectId)
  } catch (error) {
    loading.value = false
    messages.value = [
      {
        id: 'boot-error',
        role: 'assistant',
        content: `项目列表加载失败：${error.response?.data?.message || error.message}`,
        error: true
      }
    ]
  }
})
</script>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
  background: var(--bg);
}

.sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--border);
  background: #fbfbfc;
}

.brand-row {
  height: 56px;
  padding: 0 16px;
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
  color: #fff;
  background: var(--accent);
  font-weight: 700;
  font-size: 13px;
}

.brand-name {
  font-weight: 650;
}

.side-scroll {
  flex: 1;
  overflow: auto;
  padding: 4px 10px 16px;
}

.side-label {
  margin: 14px 8px 6px;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.06em;
  color: var(--text-3);
  text-transform: uppercase;
}

.side-label.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.new-conv {
  width: 22px;
  height: 22px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #fff;
  color: var(--text-2);
  line-height: 1;
  cursor: pointer;
}

.project-item,
.conv-item {
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 2px;
}

.project-item:hover,
.conv-item:hover {
  background: #f1f2f5;
}

.project-item.active,
.conv-item.active {
  background: #eef1ff;
}

.project-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-meta {
  font-size: 11px;
  color: var(--text-3);
}

.conv-item {
  font-size: 12px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.side-empty {
  padding: 12px;
  font-size: 12px;
  color: var(--text-3);
}

.user-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid var(--border);
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: #eef1ff;
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  flex: none;
}

.avatar.small {
  width: 26px;
  height: 26px;
}

.user-meta {
  flex: 1;
  min-width: 0;
  display: grid;
  line-height: 1.3;
}

.user-meta strong {
  font-size: 12px;
}

.user-meta span {
  font-size: 11px;
  color: var(--text-3);
}

.logout {
  border: 0;
  background: none;
  color: var(--text-3);
  font-size: 11px;
  cursor: pointer;
}

.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: #fff;
}

.chat-header {
  padding: 14px 28px 10px;
  border-bottom: 1px solid var(--border);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-row h2 {
  margin: 0;
  font-size: 16px;
  letter-spacing: -0.01em;
}

.status-pill {
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: var(--text-2);
  font-size: 11px;
  display: inline-flex;
  align-items: center;
}

.steps {
  display: flex;
  gap: 4px;
  margin-top: 12px;
  overflow-x: auto;
}

.step {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px 3px 3px;
  border-radius: 999px;
  color: var(--text-3);
  font-size: 11px;
  white-space: nowrap;
}

.step .dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #f3f4f6;
  font-size: 10px;
}

.step.done {
  color: var(--text-2);
}

.step.done .dot {
  background: #e8f7ee;
  color: #15803d;
}

.step.active {
  background: #eef1ff;
  color: var(--accent);
  font-weight: 650;
}

.step.active .dot {
  background: var(--accent);
  color: #fff;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 26px 32px 12px;
}

.empty {
  padding: 48px 0;
  text-align: center;
  font-size: 13px;
  color: var(--text-3);
}

.empty-state {
  max-width: 540px;
  margin: 8vh auto 0;
  text-align: center;
}

.empty-state h3 {
  margin: 0;
  font-size: 22px;
  letter-spacing: -0.02em;
}

.empty-state p {
  margin: 12px 0 24px;
  color: var(--text-2);
  line-height: 1.8;
  font-size: 13px;
}

.suggestions {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.suggestions button {
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: #fff;
  color: var(--text-2);
  font-size: 12px;
  cursor: pointer;
}

.suggestions button:hover {
  border-color: #c9ced6;
  color: var(--text);
}

.message {
  display: flex;
  gap: 10px;
  max-width: 760px;
  margin: 0 auto 22px;
}

.message.user {
  justify-content: flex-end;
}

.message-body {
  min-width: 0;
  max-width: 100%;
}

.user-bubble {
  padding: 9px 14px;
  border-radius: 12px 12px 3px 12px;
  background: #f1f2f5;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.markdown {
  font-size: 13px;
  line-height: 1.8;
  color: var(--text);
  word-break: break-word;
}

.markdown :deep(p) {
  margin: 0 0 8px;
}

.markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}

.markdown :deep(code) {
  padding: 1px 4px;
  border-radius: 4px;
  background: #f3f4f6;
  font-size: 12px;
}

.markdown :deep(table) {
  border-collapse: collapse;
  font-size: 12px;
}

.markdown :deep(th),
.markdown :deep(td) {
  border: 1px solid var(--border);
  padding: 4px 8px;
}

.markdown :deep(blockquote) {
  margin: 8px 0;
  padding-left: 10px;
  border-left: 2px solid var(--border);
  color: var(--text-2);
}

.cursor {
  display: inline-block;
  width: 7px;
  height: 14px;
  margin-left: 2px;
  background: var(--accent);
  vertical-align: -2px;
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 10px;
  color: var(--text-3);
}

.failed {
  color: #dc2626;
}

.composer {
  padding: 10px 32px 16px;
  border-top: 1px solid var(--border);
  background: #fff;
}

.input-box {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 8px 8px 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
}

.input-box:focus-within {
  border-color: #c9d1ff;
  box-shadow: 0 0 0 3px rgba(77, 107, 254, 0.08);
}

textarea {
  flex: 1;
  min-height: 28px;
  max-height: 160px;
  padding: 4px 0;
  border: 0;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  line-height: 1.7;
}

.send {
  height: 32px;
  padding: 0 16px;
  border: 0;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  flex: none;
}

.attach {
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: #fff;
  color: var(--text-2);
  font-size: 11px;
  cursor: pointer;
  flex: none;
}

.attach:disabled {
  opacity: 0.5;
  cursor: default;
}

.hidden-file {
  display: none;
}

.send:disabled {
  opacity: 0.45;
  cursor: default;
}

.disclaimer {
  max-width: 760px;
  margin: 8px auto 0;
  font-size: 10px;
  color: var(--text-3);
  text-align: center;
}

.back-home {
  margin: 6px 8px 4px;
  padding: 0;
  border: 0;
  background: none;
  color: var(--text-3);
  font-size: 11px;
  text-align: left;
  cursor: pointer;
}

.mobile-menu,
.sidebar-close {
  display: none;
}

.mobile-menu,
.panel-toggle {
  height: 28px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: #fff;
  color: var(--text-2);
  font-size: 11px;
  cursor: pointer;
}

.panel-toggle {
  margin-left: auto;
  height: 38px;
  padding: 0 20px;
  border: 0;
  border-radius: 10px;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 650;
  box-shadow: 0 6px 16px rgba(77, 107, 254, 0.28);
}

.panel-toggle:hover {
  background: #3f5cf0;
}

.panel-toggle:active {
  transform: translateY(1px);
}

.panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(420px, 100vw);
  z-index: 90;
  transform: translateX(102%);
  transition: transform 0.2s ease;
  box-shadow: -12px 0 40px rgba(15, 23, 42, 0.16);
}

.panel.open {
  transform: none;
}

.panel.wide {
  width: min(1400px, 96vw);
}

.panel-backdrop {
  display: block;
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(15, 23, 42, 0.28);
}

.sidebar-close {
  margin-left: auto;
  border: 0;
  background: none;
  color: var(--text-3);
  font-size: 11px;
  cursor: pointer;
}

.panel-close {
  position: fixed;
  top: 12px;
  right: 14px;
  z-index: 95;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: #fff;
  color: var(--text-2);
  font-size: 11px;
  cursor: pointer;
}

@media (max-width: 1200px) {
  .shell {
    grid-template-columns: 220px minmax(0, 1fr);
  }
}

@media (max-width: 767px) {
  .shell {
    grid-template-columns: minmax(0, 1fr);
    height: 100dvh;
  }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: min(280px, 84vw);
    z-index: 100;
    transform: translateX(-102%);
    transition: transform 0.2s ease;
    box-shadow: 12px 0 40px rgba(15, 23, 42, 0.16);
  }

  .sidebar.open {
    transform: none;
  }

  .mobile-menu,
  .sidebar-close {
    display: inline-flex;
    align-items: center;
  }

  .chat-header {
    padding: 10px 14px 8px;
  }

  .title-row {
    gap: 8px;
  }

  .title-row h2 {
    max-width: 52vw;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 14px;
  }

  .status-pill {
    display: none;
  }

  .steps {
    margin-top: 8px;
    gap: 2px;
  }

  .step {
    padding: 2px;
  }

  .step-label {
    display: none;
  }

.phase-guide {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 28px;
  border-bottom: 1px solid var(--border);
  background: #f7f9ff;
  font-size: 12px;
  color: var(--text-2);
}

.guide-label {
  flex: none;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 10px;
}

.guide-text {
  flex: 1;
  min-width: 0;
}

.guide-action {
  flex: none;
  height: 28px;
  padding: 0 12px;
  border: 1px solid #c9d1ff;
  border-radius: 7px;
  background: #fff;
  color: var(--accent);
  font-size: 11px;
  font-weight: 650;
  cursor: pointer;
}

.guide-action:disabled {
  opacity: 0.55;
  cursor: default;
}

  .messages {
    padding: 16px 12px 10px;
  }

  .phase-guide {
    padding: 8px 14px;
    flex-wrap: wrap;
  }

  .guide-action {
    margin-left: auto;
  }

  .message {
    max-width: 100%;
    margin-bottom: 18px;
  }

  .user-bubble {
    max-width: 88%;
  }

  .composer {
    padding: 8px 12px 10px;
  }

  .panel,
  .panel.wide {
    width: 100vw;
  }
}
</style>

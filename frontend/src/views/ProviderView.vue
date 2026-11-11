<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span>服务商工作台</span>
      </div>
      <div class="user">
        <span>{{ data?.provider?.name || auth.user?.company }}</span>
        <button @click="logout">退出</button>
      </div>
    </header>

    <main class="content">
      <div v-if="loading" class="state">正在载入工作台…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>
      <template v-else-if="data">
        <section>
          <h2>待报价询价书</h2>
          <div v-if="!data.rfps.length" class="state">暂无待处理询价。</div>
          <article v-for="rfp in data.rfps" :key="rfp.id" class="card">
            <div class="card-head">
              <strong>{{ rfp.task_code }} {{ rfp.task_name }}</strong>
              <span class="tag">{{ rfp.status }}</span>
            </div>
            <p class="muted">{{ rfp.project?.name }}</p>
            <pre class="doc">{{ rfp.content_zh }}</pre>
            <div v-if="rfp.quote" class="ok">
              已报价：{{ money(rfp.quote.amount_cents) }} {{ rfp.quote.currency }}
            </div>
            <div class="form">
              <textarea
                v-model="quoteForms[rfp.id].raw_text"
                rows="2"
                placeholder="粘贴报价文本，例如：报价合计 50 万元人民币"
              ></textarea>
              <div class="row">
                <input
                  v-model="quoteForms[rfp.id].amount"
                  type="number"
                  min="0"
                  placeholder="金额（元，可选）"
                />
                <button @click="submitQuote(rfp)">提交报价</button>
              </div>
            </div>
          </article>
        </section>

        <section>
          <h2>服务商委托合同</h2>
          <div v-if="!data.contracts.length" class="state">暂无合同。</div>
          <article v-for="contract in data.contracts" :key="contract.id" class="card">
            <div class="card-head">
              <strong>{{ contract.project?.name }} · v{{ contract.version }}</strong>
              <span class="tag">{{ contract.status }}</span>
            </div>
            <p class="muted">
              金额 {{ money(contract.total_cents) }} · 任务
              {{ (contract.task_codes || []).join('、') }}
            </p>
            <p class="muted">客户确认：{{ contract.client_confirmed_at || '未确认' }}</p>
            <button
              v-if="contract.client_confirmed_at && !contract.provider_confirmed_at"
              @click="confirmContract(contract)"
            >
              确认委托
            </button>
          </article>
        </section>

        <section>
          <h2>交付节点</h2>
          <div v-if="!data.milestones.length" class="state">暂无节点。</div>
          <article v-for="milestone in data.milestones" :key="milestone.id" class="card">
            <div class="card-head">
              <strong>{{ milestone.task_code }} {{ milestone.task_name }}</strong>
              <span class="tag">{{ milestone.status }}</span>
            </div>
            <p class="muted">
              截止 {{ milestone.due_date }} · {{ milestone.project?.name }}
            </p>
            <p class="muted">交付物：{{ milestone.deliverable }}</p>
            <textarea
              v-model="milestoneNotes[milestone.id]"
              rows="2"
              placeholder="交付说明"
            ></textarea>
            <button @click="submitMilestone(milestone)">提交交付物</button>
          </article>
        </section>

        <section>
          <h2>质询函</h2>
          <div v-if="!data.query_letters.length" class="state">暂无质询。</div>
          <article v-for="letter in data.query_letters" :key="letter.id" class="card">
            <div class="card-head">
              <strong>质询函</strong>
              <span class="tag">{{ letter.status }}</span>
            </div>
            <div v-for="finding in letter.findings" :key="finding.id" class="finding">
              <p>{{ finding.question_zh }}</p>
              <textarea
                v-model="letterReplies[letter.id][finding.id]"
                rows="2"
                placeholder="逐条回复"
              ></textarea>
            </div>
            <button @click="replyLetter(letter)">提交回复</button>
          </article>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(true)
const error = ref('')
const data = ref(null)
const quoteForms = reactive({})
const milestoneNotes = reactive({})
const letterReplies = reactive({})

function money(cents) {
  return `${(Number(cents || 0) / 100).toLocaleString('zh-CN')} 元`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.get('/provider/workbench')
    data.value = response.data.data
    for (const rfp of data.value.rfps) {
      quoteForms[rfp.id] = quoteForms[rfp.id] || { raw_text: '', amount: '' }
    }
    for (const milestone of data.value.milestones) {
      milestoneNotes[milestone.id] = milestone.submission_note || ''
    }
    for (const letter of data.value.query_letters) {
      letterReplies[letter.id] = letterReplies[letter.id] || {}
      for (const finding of letter.findings) {
        letterReplies[letter.id][finding.id] =
          letterReplies[letter.id][finding.id] || finding.reply_text || ''
      }
    }
  } catch (err) {
    error.value = err.response?.data?.message || '工作台加载失败'
  } finally {
    loading.value = false
  }
}

async function submitQuote(rfp) {
  const form = quoteForms[rfp.id]
  try {
    await client.post(`/provider/rfps/${rfp.id}/quote`, {
      raw_text: form.raw_text,
      amount_cents: form.amount ? Math.round(Number(form.amount) * 100) : undefined
    })
    ElMessage.success('报价已提交')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '提交失败')
  }
}

async function confirmContract(contract) {
  try {
    await client.post(`/provider/contracts/${contract.id}/confirm`)
    ElMessage.success('合同已确认')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '确认失败')
  }
}

async function submitMilestone(milestone) {
  try {
    await client.post(`/provider/milestones/${milestone.id}/submission`, {
      note: milestoneNotes[milestone.id] || ''
    })
    ElMessage.success('交付物已提交')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '提交失败')
  }
}

async function replyLetter(letter) {
  try {
    const replies = letter.findings.map((finding) => ({
      finding_id: finding.id,
      reply: letterReplies[letter.id][finding.id] || ''
    }))
    await client.post(`/provider/query-letters/${letter.id}/reply`, { replies })
    ElMessage.success('回复已提交')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '提交失败')
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
  align-items: center;
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
  max-width: 920px;
  margin: 0 auto;
  padding: 32px 20px 60px;
}

section {
  margin-bottom: 34px;
}

h2 {
  margin: 0 0 12px;
  font-size: 17px;
}

.card {
  margin-bottom: 12px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
}

.card-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 14px;
}

.tag {
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  background: #eef1ff;
  color: var(--accent);
  font-size: 11px;
  display: inline-flex;
  align-items: center;
}

.muted {
  margin: 6px 0;
  color: var(--text-3);
  font-size: 12px;
}

.doc {
  max-height: 180px;
  overflow: auto;
  padding: 10px;
  border-radius: 8px;
  background: #fafbfc;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.form {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.row {
  display: flex;
  gap: 8px;
}

textarea,
input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}

textarea {
  width: 100%;
  resize: vertical;
}

input {
  flex: 1;
}

button {
  height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  cursor: pointer;
}

.finding {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f2f4;
}

.finding p {
  margin: 0 0 6px;
  font-size: 13px;
}

.ok {
  margin-top: 8px;
  padding: 8px;
  border-radius: 7px;
  background: #e8f7ee;
  color: #15803d;
  font-size: 12px;
}

.state {
  padding: 30px 0;
  color: var(--text-3);
  font-size: 13px;
  text-align: center;
}

.state.error {
  color: #dc2626;
}

@media (max-width: 720px) {
  .topbar {
    padding: 0 16px;
    height: 56px;
  }

  .content {
    padding: 20px 14px 40px;
  }

  .row {
    flex-wrap: wrap;
  }

  .row input,
  .row button {
    width: 100%;
  }
}
</style>

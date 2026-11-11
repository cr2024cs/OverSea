<template>
  <div class="link-page">
    <div class="link-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>

      <div v-if="loading" class="state">正在读取项目建议书…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="proposal">
        <h1>{{ proposal.content?.title || '项目建议书' }}</h1>
        <p class="sub">版本 v{{ proposal.version }} · {{ statusLabel(proposal.status) }}</p>

        <article
          v-for="chapter in proposal.content?.chapters || []"
          :key="chapter.id"
          class="chapter"
        >
          <h2>{{ chapter.id }}. {{ chapter.title }}</h2>
          <p>{{ chapter.content }}</p>
        </article>

        <div v-if="proposal.content?.budget" class="budget">
          <h2>预算区间</h2>
          <div class="budget-row">
            <span>低</span>
            <strong>{{ money(proposal.content.budget.low_cents) }}</strong>
          </div>
          <div class="budget-row">
            <span>中</span>
            <strong>{{ money(proposal.content.budget.mid_cents) }}</strong>
          </div>
          <div class="budget-row">
            <span>高</span>
            <strong>{{ money(proposal.content.budget.high_cents) }}</strong>
          </div>
          <p class="muted">{{ proposal.content.budget.basis }}</p>
          <p class="disclaimer">{{ proposal.content.disclaimer }}</p>
        </div>

        <div v-if="proposal.status === 'client_confirmed'" class="confirmed">
          已于 {{ proposal.client_confirmed_at }} 确认。
        </div>

        <template v-else-if="proposal.status === 'revision_requested'">
          <div class="revision-note">
            已提交修改意见：{{ proposal.client_note }}
          </div>
        </template>

        <template v-else-if="proposal.status === 'sent'">
          <div class="decision">
            <button class="confirm" :disabled="busy" @click="confirm">
              {{ busy ? '提交中…' : '确认建议书' }}
            </button>

            <div class="revision">
              <textarea
                v-model="note"
                rows="3"
                placeholder="如需要修改，请填写具体意见"
              ></textarea>
              <button :disabled="busy || !note.trim()" @click="requestRevision">
                提交修改意见
              </button>
            </div>
          </div>
        </template>

        <p class="footnote">
          本页面为项目建议书确认，不构成电子签名；预算为估算区间，非正式报价。
        </p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import client from '../api/client'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const proposal = ref(null)
const busy = ref(false)
const note = ref('')

function statusLabel(value) {
  return (
    {
      generated: '待审核',
      pm_reviewed: 'PM 已审核',
      sent: '待客户确认',
      client_confirmed: '客户已确认',
      revision_requested: '客户要求修改'
    }[value] || value
  )
}

function money(cents) {
  return `${(Number(cents || 0) / 100).toLocaleString('zh-CN')} 元`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.get(`/link/${route.params.token}/proposal`)
    proposal.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '链接无效或已过期'
  } finally {
    loading.value = false
  }
}

async function confirm() {
  busy.value = true
  try {
    const response = await client.post(
      `/link/${route.params.token}/proposal/confirm`
    )
    proposal.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '确认失败'
  } finally {
    busy.value = false
  }
}

async function requestRevision() {
  if (!note.value.trim()) return
  busy.value = true
  try {
    const response = await client.post(
      `/link/${route.params.token}/proposal/revision`,
      { note: note.value }
    )
    proposal.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '提交失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.link-page {
  min-height: 100vh;
  padding: 48px 20px;
  background: var(--bg);
}

.link-card {
  max-width: 760px;
  margin: 0 auto;
  padding: 40px 48px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 32px;
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

h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: -0.02em;
}

.sub {
  margin: 8px 0 28px;
  color: var(--text-2);
  font-size: 13px;
}

.chapter {
  margin-bottom: 22px;
}

.chapter h2 {
  margin: 0 0 6px;
  font-size: 15px;
}

.chapter p {
  margin: 0;
  font-size: 13px;
  line-height: 1.9;
  color: var(--text-2);
}

.budget {
  margin-top: 28px;
  padding: 18px;
  border-radius: 10px;
  background: #f7f8fa;
}

.budget h2 {
  margin: 0 0 10px;
  font-size: 15px;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.muted {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-2);
}

.disclaimer {
  margin: 10px 0 0;
  padding: 9px;
  border-radius: 8px;
  background: #fff7e6;
  color: #92400e;
  font-size: 12px;
}

.confirmed {
  margin-top: 22px;
  padding: 12px;
  border-radius: 9px;
  background: #e8f7ee;
  color: #15803d;
  font-size: 13px;
}

.revision-note {
  margin-top: 22px;
  padding: 12px;
  border-radius: 9px;
  background: #fff7e6;
  color: #92400e;
  font-size: 13px;
}

.decision {
  margin-top: 24px;
}

.confirm {
  width: 100%;
  height: 44px;
  border: 0;
  border-radius: 9px;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
}

.confirm:disabled {
  opacity: 0.6;
  cursor: default;
}

.revision {
  margin-top: 16px;
  display: grid;
  gap: 8px;
}

.revision textarea {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 9px;
  resize: vertical;
  font-size: 13px;
  outline: none;
}

.revision textarea:focus {
  border-color: var(--accent);
}

.revision button {
  height: 36px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fff;
  color: var(--text-2);
  font-size: 13px;
  cursor: pointer;
}

.revision button:disabled {
  opacity: 0.5;
  cursor: default;
}

.footnote {
  margin: 20px 0 0;
  font-size: 11px;
  color: var(--text-3);
  text-align: center;
}

.state {
  padding: 60px 0;
  text-align: center;
  color: var(--text-2);
}

.state.error {
  color: #dc2626;
}

@media (max-width: 720px) {
  .link-card {
    padding: 28px 20px;
  }
}
</style>

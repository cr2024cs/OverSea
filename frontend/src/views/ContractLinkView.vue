<template>
  <div class="link-page">
    <div class="link-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>

      <div v-if="loading" class="state">正在读取合同…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="contract">
        <h1>委托确认单</h1>
        <p class="sub">
          版本 v{{ contract.version }} · {{ statusLabel(contract.status) }} ·
          {{ contract.actor === 'provider' ? '服务商确认' : '客户确认' }}
        </p>

        <div class="summary">
          <div><span>总价</span><strong>{{ money(contract.total_cents) }}</strong></div>
          <div><span>节点</span><strong>{{ contract.milestones?.length || 0 }} 个</strong></div>
          <div v-if="contract.provider_contract">
            <span>本服务商委托金额</span>
            <strong>{{ money(contract.provider_contract.total_cents) }}</strong>
          </div>
        </div>

        <div v-if="contract.provider_contract" class="scope">
          <h2>服务商工作范围</h2>
          <p>{{ (contract.provider_contract.scope?.task_codes || []).join('、') }}</p>
        </div>

        <h2>SLA 条款</h2>
        <div class="sla">
          <div v-for="(value, key) in contract.terms?.sla || {}" :key="key">
            <span>{{ key }}</span>
            <span>{{ value }}</span>
          </div>
        </div>

        <h2>节点表</h2>
        <article
          v-for="milestone in contract.milestones || []"
          :key="milestone.id"
          class="milestone"
        >
          <div class="milestone-head">
            <strong>{{ milestone.task_code }} {{ milestone.task_name }}</strong>
            <span>{{ milestone.status }}</span>
          </div>
          <p class="muted">
            截止 {{ milestone.due_date }} · 验收人 {{ milestone.acceptor_type }} ·
            服务商 {{ milestone.provider_name || '待定' }}
          </p>
        </article>

        <p class="disclaimer">{{ contract.terms?.disclaimer }}</p>

        <div v-if="contract.status === 'active'" class="confirmed">
          客户与服务商均已确认，合同已生效。
        </div>
        <div v-else-if="contract.actor === 'client'" class="decision">
          <p class="muted">
            当前客户确认：{{ contract.client_confirmed_at || '未确认' }}
          </p>
          <button
            v-if="contract.status === 'pending_client'"
            class="confirm"
            :disabled="busy"
            @click="confirm"
          >
            {{ busy ? '确认中…' : '确认合同与节点' }}
          </button>
          <p v-else class="muted">等待服务商确认。</p>
        </div>
        <div v-else class="decision">
          <p class="muted">
            客户确认：{{ contract.client_confirmed_at || '未确认' }} · 本服务商确认：{{
              contract.provider_contract?.provider_confirmed_at || '未确认'
            }}
          </p>
          <button
            v-if="contract.client_confirmed_at && contract.status !== 'active'"
            class="confirm"
            :disabled="busy"
            @click="confirm"
          >
            {{ busy ? '确认中…' : '确认服务商委托' }}
          </button>
          <p v-else-if="!contract.client_confirmed_at" class="muted">
            客户尚未确认，暂不能确认。
          </p>
        </div>

        <p class="footnote">本页面为委托确认，不构成电子签名；正式合同线下签署。</p>
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
const contract = ref(null)
const busy = ref(false)

function money(cents) {
  return `${(Number(cents || 0) / 100).toLocaleString('zh-CN')} 元`
}

function statusLabel(value) {
  return (
    {
      draft: '待 PM 复核',
      pending_client: '待客户确认',
      pending_provider: '待服务商确认',
      active: '已生效',
      performing: '履行中',
      completed: '已完成'
    }[value] || value
  )
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.get(`/link/${route.params.token}/contract`)
    contract.value = response.data.data
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
      `/link/${route.params.token}/contract/confirm`
    )
    contract.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '确认失败'
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
}

.sub {
  margin: 8px 0 24px;
  color: var(--text-2);
  font-size: 13px;
}

.summary {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 10px;
  background: #f7f8fa;
}

.summary div {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.scope {
  margin-top: 18px;
}

h2 {
  margin: 24px 0 8px;
  font-size: 14px;
}

.sla {
  display: grid;
  gap: 5px;
  padding: 12px;
  border-radius: 9px;
  background: #f7f8fa;
  font-size: 12px;
}

.sla div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.sla span:first-child {
  color: var(--text-3);
}

.sla span:last-child {
  text-align: right;
}

.milestone {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.milestone-head {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.muted {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-3);
}

.disclaimer {
  margin: 18px 0 0;
  padding: 11px;
  border-radius: 9px;
  background: #fff7e6;
  color: #92400e;
  font-size: 12px;
  line-height: 1.7;
}

.confirmed {
  margin-top: 20px;
  padding: 12px;
  border-radius: 9px;
  background: #e8f7ee;
  color: #15803d;
  font-size: 13px;
}

.decision {
  margin-top: 20px;
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
}

.footnote {
  margin: 18px 0 0;
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
  .link-page {
    padding: 24px 12px;
  }

  .link-card {
    padding: 24px 18px;
  }

  .sla div {
    display: grid;
    gap: 2px;
  }

  .sla span:last-child {
    text-align: left;
  }
}
</style>

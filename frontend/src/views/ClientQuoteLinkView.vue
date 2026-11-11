<template>
  <div class="link-page">
    <div class="link-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>

      <div v-if="loading" class="state">正在读取总报价…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="quote">
        <h1>客户总报价</h1>
        <p class="sub">版本 v{{ quote.version }} · {{ statusLabel(quote.status) }}</p>

        <div class="breakdown">
          <div><span>服务商费用</span><strong>{{ money(quote.provider_amount_cents) }}</strong></div>
          <div><span>关联律所费用</span><strong>{{ money(quote.lawyer_amount_cents) }}</strong></div>
          <div>
            <span>平台管理费（{{ (quote.management_fee_rate * 100).toFixed(1) }}%）</span>
            <strong>{{ money(quote.management_fee_cents) }}</strong>
          </div>
          <div class="grand">
            <span>总报价</span>
            <strong>{{ money(quote.total_cents) }}</strong>
          </div>
          <p class="muted">管理费占总报价 {{ quote.fee_percent }}%</p>
        </div>

        <p class="disclaimer">
          本报价为平台演示数据，不构成正式报价；正式合同由平台与关联律所线下签署。
        </p>

        <div v-if="quote.status === 'confirmed'" class="confirmed">
          已于 {{ quote.confirmed_at }} 确认。
        </div>
        <button v-else class="confirm" :disabled="busy" @click="confirm">
          {{ busy ? '确认中…' : '确认总报价' }}
        </button>
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
const quote = ref(null)
const busy = ref(false)

function money(cents) {
  return `${(Number(cents || 0) / 100).toLocaleString('zh-CN')} 元`
}

function statusLabel(value) {
  return (
    {
      draft: '待发送',
      sent: '待客户确认',
      confirmed: '客户已确认'
    }[value] || value
  )
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.get(`/link/${route.params.token}/client-quote`)
    quote.value = response.data.data
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
      `/link/${route.params.token}/client-quote/confirm`
    )
    quote.value = response.data.data
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
  max-width: 640px;
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

.breakdown {
  display: grid;
  gap: 8px;
  padding: 18px;
  border-radius: 10px;
  background: #f7f8fa;
}

.breakdown div {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.breakdown .grand {
  padding-top: 8px;
  margin-top: 4px;
  border-top: 1px solid var(--border);
  font-size: 15px;
}

.muted {
  margin: 6px 0 0;
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

.confirm {
  width: 100%;
  height: 44px;
  margin-top: 20px;
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

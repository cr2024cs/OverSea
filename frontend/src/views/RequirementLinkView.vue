<template>
  <div class="link-page">
    <div class="link-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>

      <div v-if="loading" class="state">正在读取需求确认书…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="requirement">
        <h1>{{ requirement.title }}</h1>
        <p class="sub">
          {{ requirement.project_name }} · {{ requirement.client_name }}
        </p>

        <p class="scope">{{ requirement.scope_statement }}</p>

        <h2>事实基础</h2>
        <div class="facts">
          <div v-for="fact in requirement.facts" :key="fact.key" class="fact-row">
            <span class="key">{{ fact.key }}</span>
            <span class="value">{{ fact.value }}</span>
            <span class="tag">{{ statusLabel(fact.status) }}</span>
          </div>
        </div>

        <h2>任务范围</h2>
        <p class="muted">
          共 {{ requirement.task_summary.total }} 项 · 总周期
          {{ requirement.task_summary.total_days }} 天
        </p>
        <p class="muted">
          关键路径：{{ (requirement.task_summary.critical_path || []).join(' → ') }}
        </p>

        <p class="disclaimer">{{ requirement.disclaimer }}</p>

        <div v-if="requirement.confirmed_at" class="confirmed">
          已于 {{ requirement.confirmed_at }} 确认。重复点击不会覆盖首次确认时间。
        </div>
        <button v-else class="confirm" :disabled="confirming" @click="confirm">
          {{ confirming ? '正在确认…' : '确认需求范围' }}
        </button>

        <p class="footnote">
          本页面为委托确认，不构成电子签名；正式合同由平台与关联律所线下签署。
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
const requirement = ref(null)
const confirming = ref(false)

function statusLabel(value) {
  return (
    {
      confirmed: '已确认',
      assumption: '客户假设',
      unknown: '未知'
    }[value] || value
  )
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await client.get(`/link/${route.params.token}/requirement`)
    requirement.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '链接无效或已过期'
  } finally {
    loading.value = false
  }
}

async function confirm() {
  confirming.value = true
  try {
    const response = await client.post(
      `/link/${route.params.token}/requirement/confirm`
    )
    requirement.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '确认失败，请稍后重试'
  } finally {
    confirming.value = false
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
  max-width: 720px;
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
  margin-bottom: 36px;
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
  margin: 8px 0 24px;
  color: var(--text-2);
  font-size: 13px;
}

.scope {
  margin: 0 0 28px;
  padding: 14px;
  border-radius: 9px;
  background: #f7f8fa;
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-2);
}

h2 {
  margin: 26px 0 10px;
  font-size: 14px;
}

.facts {
  border-top: 1px solid var(--border);
}

.fact-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}

.key {
  width: 120px;
  flex: none;
  color: var(--text-2);
}

.value {
  flex: 1;
}

.tag {
  padding: 1px 7px;
  border-radius: 999px;
  background: #f3f4f6;
  color: var(--text-2);
  font-size: 11px;
}

.muted {
  margin: 4px 0;
  color: var(--text-2);
  font-size: 12px;
}

.disclaimer {
  margin: 24px 0 0;
  padding: 12px;
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
  cursor: default;
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
  .link-card {
    padding: 28px 20px;
  }
}
</style>

<template>
  <div class="link-page">
    <div class="link-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>

      <div v-if="loading" class="state">正在读取询价书…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="rfp">
        <h1>询价书 · {{ rfp.task_code }} {{ rfp.task_name }}</h1>
        <p class="sub">请提交报价、假设、不含项与付款条件。</p>

        <div class="doc-grid">
          <section>
            <h2>中文</h2>
            <pre class="doc">{{ rfp.content_zh }}</pre>
          </section>
          <section>
            <h2>English</h2>
            <pre class="doc">{{ rfp.content_en }}</pre>
          </section>
        </div>

        <div v-if="rfp.quote" class="submitted">
          已收到报价：{{ money(rfp.quote.amount_cents) }} {{ rfp.quote.currency }}
        </div>

        <form class="form" @submit.prevent="submit">
          <label>
            <span>报价说明（可粘贴：如“报价合计 52 万元人民币”）</span>
            <textarea v-model="rawText" rows="4" placeholder="请输入或粘贴报价"></textarea>
          </label>
          <div class="row">
            <label>
              <span>金额（元，可选）</span>
              <input v-model="amountYuan" type="number" min="0" />
            </label>
            <label>
              <span>币种</span>
              <select v-model="currency">
                <option value="CNY">CNY</option>
                <option value="USD">USD</option>
                <option value="THB">THB</option>
              </select>
            </label>
          </div>
          <label>
            <span>假设</span>
            <textarea v-model="assumptions" rows="2"></textarea>
          </label>
          <label>
            <span>不含项</span>
            <textarea v-model="exclusions" rows="2"></textarea>
          </label>
          <label>
            <span>付款条件</span>
            <input v-model="paymentTerms" />
          </label>
          <button type="submit" :disabled="busy">
            {{ busy ? '提交中…' : '提交报价' }}
          </button>
        </form>
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
const rfp = ref(null)
const busy = ref(false)
const rawText = ref('')
const amountYuan = ref('')
const currency = ref('CNY')
const assumptions = ref('')
const exclusions = ref('')
const paymentTerms = ref('')

function money(cents) {
  return `${(Number(cents || 0) / 100).toLocaleString('zh-CN')} 元`
}

async function load() {
  loading.value = true
  try {
    const response = await client.get(`/rfp-link/${route.params.token}`)
    rfp.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '链接无效或已过期'
  } finally {
    loading.value = false
  }
}

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const payload = {
      raw_text: rawText.value,
      currency: currency.value,
      assumptions: assumptions.value,
      exclusions: exclusions.value,
      payment_terms: paymentTerms.value
    }
    if (amountYuan.value) {
      payload.amount_cents = Math.round(Number(amountYuan.value) * 100)
    }
    await client.post(`/rfp-link/${route.params.token}/quote`, payload)
    await load()
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
  padding: 40px 20px;
  background: var(--bg);
}

.link-card {
  max-width: 900px;
  margin: 0 auto;
  padding: 36px 44px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
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
  font-size: 22px;
}

.sub {
  margin: 8px 0 22px;
  color: var(--text-2);
  font-size: 13px;
}

.doc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.doc-grid h2 {
  margin: 0 0 6px;
  font-size: 13px;
}

.doc {
  margin: 0;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fafbfc;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.8;
  white-space: pre-wrap;
  max-height: 340px;
  overflow: auto;
}

.submitted {
  margin-top: 16px;
  padding: 12px;
  border-radius: 9px;
  background: #e8f7ee;
  color: #15803d;
  font-size: 13px;
}

.form {
  display: grid;
  gap: 12px;
  margin-top: 22px;
}

label {
  display: grid;
  gap: 5px;
  font-size: 12px;
  color: var(--text-2);
}

input,
textarea,
select {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}

input:focus,
textarea:focus,
select:focus {
  border-color: var(--accent);
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

button {
  height: 42px;
  border: 0;
  border-radius: 9px;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
}

button:disabled {
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
    padding: 24px 18px;
  }

  .doc-grid {
    grid-template-columns: 1fr;
  }

  .row {
    grid-template-columns: 1fr;
  }
}
</style>

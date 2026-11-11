<template>
  <div class="link-page">
    <div class="link-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>

      <div v-if="loading" class="state">正在读取质询函…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="letter">
        <h1>质询函回复</h1>
        <p class="sub">状态：{{ letter.status }}</p>
        <pre class="content">{{ letter.content }}</pre>

        <div v-if="letter.status === 'closed'" class="confirmed">
          质询已关闭。
        </div>
        <template v-else>
          <section
            v-for="finding in letter.findings || []"
            :key="finding.id"
            class="finding"
          >
            <div class="finding-head">
              <strong>[{{ finding.category }}] {{ finding.severity }}</strong>
              <span>{{ finding.conclusion_level }}</span>
            </div>
            <p class="muted">原文：{{ finding.quote_text }}</p>
            <p class="question">{{ finding.question_zh }}</p>
            <textarea
              v-model="replies[finding.id]"
              rows="3"
              placeholder="请逐条回复"
            ></textarea>
          </section>

          <button :disabled="busy" @click="submit">
            {{ busy ? '提交中…' : '提交回复' }}
          </button>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import client from '../api/client'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const letter = ref(null)
const busy = ref(false)
const replies = reactive({})

async function load() {
  loading.value = true
  try {
    const response = await client.get(`/link/${route.params.token}/query-letter`)
    letter.value = response.data.data
    for (const finding of letter.value.findings || []) {
      replies[finding.id] = finding.reply_text || ''
    }
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
    const payload = (letter.value.findings || []).map((finding) => ({
      finding_id: finding.id,
      reply: replies[finding.id] || ''
    }))
    await client.post(`/link/${route.params.token}/query-letter/reply`, {
      replies: payload
    })
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
  margin-bottom: 30px;
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
  font-size: 24px;
}

.sub {
  margin: 8px 0 18px;
  color: var(--text-2);
  font-size: 13px;
}

.content {
  max-height: 220px;
  overflow: auto;
  padding: 12px;
  border-radius: 9px;
  background: #fafbfc;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.finding {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 9px;
}

.finding-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.question {
  margin: 8px 0;
  padding: 8px;
  border-radius: 7px;
  background: #f7f8fa;
  font-size: 12px;
  line-height: 1.6;
}

.muted {
  margin: 4px 0;
  color: var(--text-3);
  font-size: 11px;
}

textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 12px;
  resize: vertical;
  outline: none;
}

textarea:focus {
  border-color: var(--accent);
}

button {
  width: 100%;
  height: 42px;
  margin-top: 18px;
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

.confirmed {
  margin-top: 18px;
  padding: 12px;
  border-radius: 9px;
  background: #e8f7ee;
  color: #15803d;
  font-size: 13px;
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
}
</style>

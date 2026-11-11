<template>
  <div class="link-page">
    <div class="link-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea · 专家盲评</span>
      </div>

      <div v-if="loading" class="state">正在读取评审任务…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="task">
        <h1>{{ task.task_code }} {{ task.task_name }}</h1>
        <p class="sub">{{ task.project_name }} · 第 {{ task.rounds }} 轮</p>

        <div class="brief">
          <h2>交付物与验收标准</h2>
          <p class="muted">交付物：{{ task.deliverable || '—' }}</p>
          <p class="muted">验收标准：{{ task.acceptance_criteria || '—' }}</p>
          <p class="muted">提交说明：{{ task.submission_note || '—' }}</p>
          <p v-if="task.submission_files?.length" class="muted">
            附件：{{ task.submission_files.join('、') }}
          </p>
        </div>

        <div v-if="task.locked" class="confirmed">
          评分已提交并锁定，不可修改。
        </div>

        <form v-else class="form" @submit.prevent="submit">
          <h2>评分</h2>
          <label v-for="(weight, key) in task.weights" :key="key">
            <span>{{ label(key) }}（权重 {{ Math.round(weight * 100) }}%）</span>
            <input v-model.number="scores[key]" type="number" min="0" max="100" />
          </label>

          <label>
            <span>评审意见（必填）</span>
            <textarea v-model="comment" rows="4"></textarea>
          </label>

          <label class="check">
            <input v-model="conflict" type="checkbox" />
            <span>本人声明与本项目无利益冲突</span>
          </label>

          <p class="muted">加权总分：{{ total }}</p>
          <button type="submit" :disabled="busy">
            {{ busy ? '提交中…' : '提交评分并锁定' }}
          </button>
        </form>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import client from '../api/client'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const task = ref(null)
const busy = ref(false)
const comment = ref('')
const conflict = ref(false)
const scores = ref({
  completeness: 80,
  quality: 80,
  executability: 80,
  timeliness: 80
})

const total = computed(() => {
  if (!task.value) return 0
  return Object.entries(task.value.weights).reduce(
    (sum, [key, weight]) => sum + (Number(scores.value[key]) || 0) * weight,
    0
  ).toFixed(2)
})

function label(key) {
  return (
    {
      completeness: '完整性',
      quality: '专业质量',
      executability: '可执行性',
      timeliness: '及时性'
    }[key] || key
  )
}

async function load() {
  loading.value = true
  try {
    const response = await client.get(`/link/${route.params.token}/expert`)
    task.value = response.data.data
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
    await client.post(`/link/${route.params.token}/expert/review`, {
      scores: scores.value,
      comment: comment.value,
      conflict_declared: conflict.value
    })
    task.value.locked = true
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
  font-size: 24px;
}

.sub {
  margin: 8px 0 22px;
  color: var(--text-2);
  font-size: 13px;
}

h2 {
  margin: 0 0 8px;
  font-size: 14px;
}

.brief {
  padding: 14px;
  border-radius: 10px;
  background: #f7f8fa;
}

.muted {
  margin: 4px 0;
  font-size: 12px;
  color: var(--text-2);
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

label.check {
  display: flex;
  align-items: center;
  gap: 8px;
}

input,
textarea {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}

input:focus,
textarea:focus {
  border-color: var(--accent);
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

.confirmed {
  margin-top: 20px;
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
  .link-card {
    padding: 28px 20px;
  }
}
</style>

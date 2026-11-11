<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span>专家评审工作台</span>
      </div>
      <div class="user">
        <span>{{ auth.user?.name }}</span>
        <button @click="logout">退出</button>
      </div>
    </header>

    <main class="content">
      <div v-if="loading" class="state">正在载入评审任务…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>
      <template v-else>
        <div v-if="!items.length" class="state">暂无分配给你的评审任务。</div>

        <article
          v-for="item in items"
          :key="item.milestone_id"
          class="card"
          :class="{ active: selected?.milestone_id === item.milestone_id }"
          @click="select(item)"
        >
          <div class="card-head">
            <strong>{{ item.task_code }} {{ item.task_name }}</strong>
            <span class="tag">{{ item.locked ? '已锁定' : item.status }}</span>
          </div>
          <p class="muted">{{ item.project_name }} · 截止 {{ item.due_date }}</p>
          <p class="muted">交付物：{{ item.deliverable }}</p>
        </article>

        <section v-if="selected" class="review">
          <h2>{{ selected.task_code }} {{ selected.task_name }}</h2>
          <p class="muted">验收标准：{{ selected.acceptance_criteria }}</p>
          <p class="muted">提交说明：{{ selected.submission_note || '—' }}</p>

          <div v-if="selected.locked" class="ok">评分已提交并锁定。</div>
          <form v-else @submit.prevent="submit">
            <label v-for="(weight, key) in selected.weights" :key="key">
              <span>{{ label(key) }}（{{ Math.round(weight * 100) }}%）</span>
              <input v-model.number="scores[key]" type="number" min="0" max="100" />
            </label>
            <label>
              <span>评审意见</span>
              <textarea v-model="comment" rows="4"></textarea>
            </label>
            <label class="check">
              <input v-model="conflict" type="checkbox" />
              <span>本人声明与本项目无利益冲突</span>
            </label>
            <p class="muted">加权总分：{{ total }}</p>
            <button type="submit" :disabled="busy">提交评分并锁定</button>
          </form>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(true)
const error = ref('')
const items = ref([])
const selected = ref(null)
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
  if (!selected.value) return 0
  return Object.entries(selected.value.weights).reduce(
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
    const response = await client.get('/expert/workbench')
    items.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function select(item) {
  selected.value = item
  comment.value = ''
  conflict.value = false
  scores.value = {
    completeness: 80,
    quality: 80,
    executability: 80,
    timeliness: 80
  }
}

async function submit() {
  busy.value = true
  try {
    await client.post(`/expert/milestones/${selected.value.milestone_id}/review`, {
      scores: scores.value,
      comment: comment.value,
      conflict_declared: conflict.value
    })
    ElMessage.success('评分已提交并锁定')
    await load()
    selected.value = items.value.find(
      (item) => item.milestone_id === selected.value.milestone_id
    )
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '提交失败')
  } finally {
    busy.value = false
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
  max-width: 760px;
  margin: 0 auto;
  padding: 30px 20px 60px;
}

.card {
  margin-bottom: 10px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
}

.card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(77, 107, 254, 0.08);
}

.card-head {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.tag {
  padding: 1px 8px;
  border-radius: 999px;
  background: #eef1ff;
  color: var(--accent);
  font-size: 11px;
}

.muted {
  margin: 6px 0;
  font-size: 12px;
  color: var(--text-3);
}

.review {
  margin-top: 22px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
}

h2 {
  margin: 0 0 8px;
  font-size: 17px;
}

form {
  display: grid;
  gap: 12px;
  margin-top: 14px;
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

button {
  height: 40px;
  border: 0;
  border-radius: 9px;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
}

.ok {
  padding: 10px;
  border-radius: 8px;
  background: #e8f7ee;
  color: #15803d;
  font-size: 13px;
}

.state {
  padding: 40px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
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

  .review {
    padding: 14px;
  }
}
</style>

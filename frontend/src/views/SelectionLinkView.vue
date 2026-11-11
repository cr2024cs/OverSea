<template>
  <div class="link-page">
    <div class="link-card">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>

      <div v-if="loading" class="state">正在读取服务目录…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="catalog">
        <h1>选择服务</h1>
        <p class="sub">勾选需要的服务项；缺少前置服务时我们会提示，但不会阻止提交。</p>

        <section v-for="stage in catalog.stages" :key="stage.stage" class="stage">
          <h2>{{ stage.stage }} · {{ stage.stage_label }}</h2>
          <label
            v-for="item in stage.items"
            :key="item.code"
            class="item"
            :class="{ checked: selected.includes(item.code) }"
          >
            <input v-model="selected" type="checkbox" :value="item.code" />
            <span class="code">{{ item.code }}</span>
            <span class="name">{{ item.name }}</span>
            <span class="fee">{{ money(item.fee_min_cents) }}–{{ money(item.fee_max_cents) }}</span>
          </label>
        </section>

        <div v-if="warnings.length" class="warnings">
          <p v-for="warning in warnings" :key="warning">{{ warning }}</p>
        </div>

        <p v-if="saved" class="saved">已保存 {{ selected.length }} 项服务。</p>
        <button class="submit" :disabled="busy" @click="save">
          {{ busy ? '保存中…' : '确认服务选择' }}
        </button>
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
const catalog = ref(null)
const selected = ref([])
const busy = ref(false)
const saved = ref(false)

const warnings = computed(() => {
  if (!catalog.value) return []
  const items = catalog.value.stages.flatMap((stage) => stage.items)
  const byCode = Object.fromEntries(items.map((item) => [item.code, item]))
  const chosen = new Set(selected.value)
  const result = []
  for (const code of selected.value) {
    const item = byCode[code]
    if (!item) continue
    for (const predecessor of item.predecessors || []) {
      if (!chosen.has(predecessor)) {
        result.push(`${code} 需要前置 ${predecessor}，请同时选择或确认平台另行安排`)
      }
    }
  }
  return result
})

function money(cents) {
  return `${(Number(cents || 0) / 100).toLocaleString('zh-CN')} 元`
}

async function load() {
  loading.value = true
  try {
    const response = await client.get(`/link/${route.params.token}/selection`)
    catalog.value = response.data.data
    selected.value = [...(response.data.data.selection.codes || [])]
  } catch (err) {
    error.value = err.response?.data?.message || '链接无效或已过期'
  } finally {
    loading.value = false
  }
}

async function save() {
  busy.value = true
  error.value = ''
  try {
    const response = await client.post(
      `/link/${route.params.token}/selection`,
      { codes: selected.value }
    )
    catalog.value = response.data.data
    selected.value = [...(response.data.data.selection.codes || [])]
    saved.value = true
  } catch (err) {
    error.value = err.response?.data?.message || '保存失败'
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

.stage h2 {
  margin: 20px 0 8px;
  font-size: 14px;
}

.item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #f1f2f4;
  font-size: 13px;
  cursor: pointer;
}

.item.checked {
  background: #eef1ff;
}

.item input {
  accent-color: var(--accent);
}

.code {
  width: 34px;
  color: var(--text-3);
  font-size: 11px;
}

.name {
  flex: 1;
}

.fee {
  color: var(--text-3);
  font-size: 11px;
}

.warnings {
  margin-top: 18px;
  padding: 12px;
  border-radius: 9px;
  background: #fff7e6;
  color: #92400e;
  font-size: 12px;
  line-height: 1.7;
}

.warnings p {
  margin: 0 0 4px;
}

.saved {
  margin-top: 16px;
  color: #15803d;
  font-size: 13px;
}

.submit {
  width: 100%;
  height: 44px;
  margin-top: 18px;
  border: 0;
  border-radius: 9px;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
}

.submit:disabled {
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

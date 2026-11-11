<template>
  <el-dialog
    :model-value="modelValue"
    width="min(680px, 94vw)"
    top="8vh"
    @update:model-value="close"
  >
    <template #header>
      <div class="head">
        <span class="title">{{ chunk?.title || '知识库片段' }}</span>
        <span v-if="chunk?.stale" class="stale">需复核</span>
      </div>
    </template>

    <div v-if="loading" class="state">正在读取…</div>
    <div v-else-if="error" class="state error">{{ error }}</div>
    <template v-else-if="chunk">
      <p class="path">{{ chunk.doc_code }} · {{ chunk.heading_path }}</p>
      <p class="muted">
        最后复核 {{ chunk.last_reviewed || '—' }} · 字符 {{ chunk.char_start }}–{{ chunk.char_end }}
      </p>
      <pre class="content">{{ chunk.content }}</pre>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import client from '../api/client'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  chunkId: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const error = ref('')
const chunk = ref(null)

function close(value) {
  emit('update:modelValue', value)
}

async function load() {
  if (!props.modelValue || !props.chunkId) return
  loading.value = true
  error.value = ''
  try {
    const response = await client.get(`/knowledge/chunks/${props.chunkId}`)
    chunk.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '读取失败'
  } finally {
    loading.value = false
  }
}

watch(() => [props.modelValue, props.chunkId], load, { deep: true })
</script>

<style scoped>
.head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title {
  font-weight: 650;
}

.stale {
  padding: 1px 7px;
  border-radius: 999px;
  background: #fff7e6;
  color: #b45309;
  font-size: 11px;
}

.path {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--text-2);
}

.muted {
  margin: 0 0 12px;
  font-size: 11px;
  color: var(--text-3);
}

.content {
  max-height: 56vh;
  overflow: auto;
  margin: 0;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fafbfc;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.9;
  white-space: pre-wrap;
}

.state {
  padding: 40px 0;
  text-align: center;
  color: var(--text-2);
}

.state.error {
  color: #dc2626;
}
</style>

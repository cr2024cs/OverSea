<template>
  <el-dialog
    :model-value="modelValue"
    width="min(760px, 94vw)"
    top="6vh"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <template #header>
      <div class="doc-header">
        <span class="doc-title">{{ filename || '原文' }}</span>
        <span class="doc-hint">高亮为引用位置</span>
      </div>
    </template>

    <div v-if="loading" class="doc-loading">正在读取原文…</div>
    <div v-else-if="error" class="doc-loading">{{ error }}</div>
    <pre v-else class="doc-text"><span
      v-for="(segment, index) in segments"
      :key="index"
      :class="{ hit: segment.hit }"
    >{{ segment.text }}</span></pre>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import client from '../api/client'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  citation: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const error = ref('')
const document = ref(null)

const filename = computed(
  () => document.value?.filename || props.citation?.filename || '原文'
)

const segments = computed(() => {
  if (!document.value || !props.citation) return []
  const text = document.value.text || ''
  const start = Math.max(0, Number(props.citation.char_start ?? 0))
  const end = Math.min(text.length, Number(props.citation.char_end ?? 0))
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    return [{ text, hit: false }]
  }
  return [
    { text: text.slice(0, start), hit: false },
    { text: text.slice(start, end), hit: true },
    { text: text.slice(end), hit: false }
  ]
})

function close(value) {
  emit('update:modelValue', value)
}

async function load() {
  const docId = props.citation?.doc_id
  if (!props.modelValue || !docId) return
  loading.value = true
  error.value = ''
  document.value = null
  try {
    const response = await client.get(`/documents/${docId}`)
    document.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '原文加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => [props.modelValue, props.citation], load, { deep: true })
</script>

<style scoped>
.doc-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.doc-title {
  font-weight: 650;
}

.doc-hint {
  font-size: 12px;
  color: var(--text-3);
}

.doc-loading {
  padding: 40px 0;
  text-align: center;
  color: var(--text-2);
}

.doc-text {
  max-height: 62vh;
  overflow: auto;
  margin: 0;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fafbfc;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
}

.doc-text :deep(.hit),
.doc-text .hit {
  background: #fff1a8;
  padding: 1px 2px;
  border-radius: 3px;
}
</style>

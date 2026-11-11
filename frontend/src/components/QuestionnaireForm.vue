<template>
  <div class="questionnaire">
    <div class="q-head">
      <div>
        <h3>{{ questionnaire.title }}</h3>
        <p>第 {{ currentIndex + 1 }} / {{ visibleSections.length }} 节 · 约 {{ questionnaire.estimated_minutes }} 分钟</p>
      </div>
      <span class="answered">{{ answeredCount }} / {{ totalVisibleQuestions }} 已回答</span>
    </div>

    <div class="progress">
      <span
        v-for="(section, index) in visibleSections"
        :key="section.id"
        class="seg"
        :class="{ active: index <= currentIndex }"
      ></span>
    </div>

    <section v-if="currentSection" class="section">
      <h4>{{ currentSection.id }} · {{ currentSection.title }}</h4>

      <article v-for="question in currentQuestions" :key="question.id" class="question">
        <div class="q-title">
          <span>{{ question.id }}. {{ question.text }}</span>
          <span v-if="question.required" class="required">必填</span>
        </div>
        <p v-if="question.help" class="help">{{ question.help }}</p>

        <div v-if="question.type === 'single'" class="options">
          <button
            v-for="option in question.options"
            :key="option.code"
            type="button"
            class="option"
            :class="{ selected: answers[question.id] === option.code }"
            @click="selectSingle(question.id, option.code)"
          >
            {{ option.label }}
            <span v-if="option.followup" class="followup">需追问</span>
          </button>
        </div>

        <div v-else-if="question.type === 'multi'" class="options">
          <button
            v-for="option in question.options"
            :key="option.code"
            type="button"
            class="option"
            :class="{ selected: isMultiSelected(question.id, option.code) }"
            @click="toggleMulti(question, option)"
          >
            {{ option.label }}
            <span v-if="option.followup" class="followup">需追问</span>
            <span v-if="option.exclusive" class="followup">互斥</span>
          </button>
        </div>

        <textarea
          v-else
          v-model="answers[question.id]"
          rows="3"
          placeholder="请输入"
        ></textarea>

        <p v-if="showErrors && isMissing(question)" class="error">此项为必填</p>
      </article>
    </section>

    <p v-if="message" class="error">{{ message }}</p>

    <div class="actions">
      <button type="button" class="ghost" :disabled="currentIndex === 0" @click="prev">
        上一节
      </button>
      <button
        v-if="currentIndex < visibleSections.length - 1"
        type="button"
        class="primary"
        @click="next"
      >
        下一节
      </button>
      <button v-else type="button" class="primary" @click="submit">
        完成问卷
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  questionnaire: { type: Object, required: true },
  project: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['complete'])
const answers = defineModel({ type: Object, default: () => ({}) })

const currentIndex = ref(0)
const showErrors = ref(false)
const message = ref('')

const sectionVisibility = computed(() => {
  const result = {}
  for (const section of props.questionnaire.sections || []) {
    result[section.id] = conditionMet(section.show_if)
  }
  return result
})

const visibleSections = computed(() =>
  (props.questionnaire.sections || []).filter(
    (section) => sectionVisibility.value[section.id] !== false
  )
)

const currentSection = computed(() => visibleSections.value[currentIndex.value])

const currentQuestions = computed(() => {
  if (!currentSection.value) return []
  return (props.questionnaire.questions || []).filter(
    (question) =>
      question.section === currentSection.value.id && conditionMet(question.show_if)
  )
})

const totalVisibleQuestions = computed(() =>
  (props.questionnaire.questions || []).filter((question) => {
    if (sectionVisibility.value[question.section] === false) return false
    return conditionMet(question.show_if)
  }).length
)

const answeredCount = computed(
  () =>
    (props.questionnaire.questions || []).filter((question) => {
      if (sectionVisibility.value[question.section] === false) return false
      if (!conditionMet(question.show_if)) return false
      const value = answers.value[question.id]
      return Array.isArray(value) ? value.length > 0 : Boolean(value)
    }).length
)

function values(questionId) {
  const value = answers.value[questionId]
  if (value === undefined || value === null) return []
  return Array.isArray(value) ? value : [value]
}

function conditionMet(condition) {
  if (!condition) return true
  if (condition.always) return true
  if (condition.all) return condition.all.every(conditionMet)
  if (condition.any) return condition.any.some(conditionMet)
  if (condition.any_followup) {
    return (props.questionnaire.questions || []).some((question) =>
      (question.options || []).some(
        (option) => option.followup && values(question.id).includes(option.code)
      )
    )
  }
  if (condition.q) {
    const selected = values(condition.q)
    if (condition.in) return selected.some((value) => condition.in.includes(value))
    if (condition.not_in) {
      return (
        selected.length > 0 &&
        selected.every((value) => !condition.not_in.includes(value))
      )
    }
  }
  if (condition.project) {
    const value = props.project[condition.project]
    if (condition.in) return condition.in.includes(value)
    if (condition.not_in) return !condition.not_in.includes(value)
  }
  return false
}

function selectSingle(questionId, code) {
  answers.value = { ...answers.value, [questionId]: code }
  message.value = ''
}

function isMultiSelected(questionId, code) {
  return values(questionId).includes(code)
}

function toggleMulti(question, option) {
  const current = [...values(question.id)]
  const selected = current.includes(option.code)

  if (option.exclusive) {
    answers.value = {
      ...answers.value,
      [question.id]: selected ? [] : [option.code]
    }
    message.value = ''
    return
  }

  const withoutExclusive = current.filter(
    (code) =>
      !(question.options || []).some(
        (item) => item.code === code && item.exclusive
      )
  )
  let next = selected
    ? withoutExclusive.filter((code) => code !== option.code)
    : [...withoutExclusive, option.code]

  if (question.max_select && next.length > question.max_select) {
    message.value = `最多选择 ${question.max_select} 项`
    return
  }
  answers.value = { ...answers.value, [question.id]: next }
  message.value = ''
}

function isMissing(question) {
  if (!question.required) return false
  const value = answers.value[question.id]
  return Array.isArray(value) ? value.length === 0 : !value
}

function validateCurrent() {
  showErrors.value = true
  if (currentQuestions.value.some(isMissing)) {
    message.value = '请完成本节必填项'
    return false
  }
  message.value = ''
  return true
}

function next() {
  if (!validateCurrent()) return
  currentIndex.value += 1
  showErrors.value = false
}

function prev() {
  if (currentIndex.value > 0) {
    currentIndex.value -= 1
    showErrors.value = false
    message.value = ''
  }
}

function validateAll() {
  showErrors.value = true
  const questions = props.questionnaire.questions || []
  for (let index = 0; index < visibleSections.value.length; index += 1) {
    const section = visibleSections.value[index]
    const sectionQuestions = questions.filter(
      (question) =>
        question.section === section.id && conditionMet(question.show_if)
    )
    if (sectionQuestions.some(isMissing)) {
      currentIndex.value = index
      message.value = `请完成“${section.title}”中的必填项`
      return false
    }
  }
  return true
}

function submit() {
  if (!validateAll()) return
  emit('complete', answers.value)
}

function applyPrefill() {
  const nextAnswers = { ...answers.value }
  const industryMap = { manufacturing: 'auto', trading: 'consumer' }
  const entryMap = {
    greenfield: 'greenfield',
    ma: 'acquisition',
    jv: 'jv'
  }
  if (!nextAnswers.Q02 && industryMap[props.project.industry]) {
    nextAnswers.Q02 = industryMap[props.project.industry]
  }
  if (!nextAnswers.Q06 && entryMap[props.project.entry_mode]) {
    nextAnswers.Q06 = entryMap[props.project.entry_mode]
  }
  answers.value = nextAnswers
}

watch(
  () => [props.questionnaire, props.project.industry, props.project.entry_mode],
  applyPrefill,
  { immediate: true, deep: true }
)

watch(visibleSections, () => {
  if (currentIndex.value >= visibleSections.value.length) {
    currentIndex.value = Math.max(0, visibleSections.value.length - 1)
  }
})

defineExpose({ validateAll })
</script>

<style scoped>
.questionnaire {
  display: grid;
  gap: 14px;
}

.q-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.q-head h3 {
  margin: 0;
  font-size: 16px;
}

.q-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-3);
}

.answered {
  flex: none;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef1ff;
  color: var(--accent);
  font-size: 11px;
}

.progress {
  display: flex;
  gap: 4px;
}

.seg {
  flex: 1;
  height: 4px;
  border-radius: 999px;
  background: #eef0f3;
}

.seg.active {
  background: var(--accent);
}

.section {
  min-height: 300px;
}

.section h4 {
  margin: 0 0 14px;
  font-size: 15px;
}

.question {
  margin-bottom: 18px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f1f2f4;
}

.q-title {
  display: flex;
  gap: 8px;
  align-items: baseline;
  font-size: 13px;
  font-weight: 600;
}

.required {
  color: #dc2626;
  font-size: 10px;
  font-weight: 400;
}

.help {
  margin: 4px 0 10px;
  font-size: 11px;
  color: var(--text-3);
}

.options {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 6px;
  margin-top: 8px;
}

.option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 36px;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--text-2);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.option:hover {
  border-color: #c9d1ff;
}

.option.selected {
  border-color: var(--accent);
  background: #eef1ff;
  color: var(--accent);
  font-weight: 600;
}

.followup {
  flex: none;
  padding: 0 5px;
  border-radius: 999px;
  background: #fff7e6;
  color: #b45309;
  font-size: 9px;
}

textarea {
  width: 100%;
  margin-top: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  resize: vertical;
  outline: none;
}

textarea:focus {
  border-color: var(--accent);
}

.error {
  margin: 6px 0 0;
  color: #dc2626;
  font-size: 11px;
}

.actions {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding-top: 6px;
}

.primary,
.ghost {
  height: 38px;
  padding: 0 18px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}

.primary {
  border: 0;
  background: var(--accent);
  color: #fff;
}

.ghost {
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text-2);
}

.ghost:disabled {
  opacity: 0.5;
  cursor: default;
}

@media (max-width: 720px) {
  .options {
    grid-template-columns: 1fr;
  }

  .q-head {
    display: grid;
  }
}
</style>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="step === 0 ? '新建出海项目' : '项目问卷'"
    width="min(860px, 96vw)"
    top="5vh"
    @update:model-value="close"
  >
    <div v-if="auth.user?.role === 'client'" class="steps">
      <span :class="{ active: step === 0 }">1 基本信息</span>
      <span class="line"></span>
      <span :class="{ active: step === 1 }">2 项目问卷</span>
    </div>

    <div v-if="step === 0" class="form">
      <label>
        <span>项目名称</span>
        <input v-model.trim="form.name" placeholder="不填则自动生成" />
      </label>

      <label v-if="auth.user?.role !== 'client'">
        <span>客户名称</span>
        <input v-model.trim="form.client_name" placeholder="客户公司名称" />
      </label>
      <p v-else class="hint">客户：{{ auth.user?.company || auth.user?.name }}</p>

      <div class="row">
        <label>
          <span>国家</span>
          <select v-model="form.country">
            <option v-for="item in options.country || []" :key="item.code" :value="item.code">
              {{ item.name }}
            </option>
          </select>
        </label>
        <label>
          <span>行业</span>
          <select v-model="form.industry">
            <option v-for="item in options.industry || []" :key="item.code" :value="item.code">
              {{ item.name }}
            </option>
          </select>
        </label>
      </div>

      <div class="row">
        <label>
          <span>出海方式</span>
          <select v-model="form.entry_mode">
            <option v-for="item in options.entry_mode || []" :key="item.code" :value="item.code">
              {{ item.name }}
            </option>
          </select>
        </label>
        <label>
          <span>币种</span>
          <select v-model="form.currency">
            <option v-for="item in options.currency || []" :key="item.code" :value="item.code">
              {{ item.name }}
            </option>
          </select>
        </label>
      </div>

      <label>
        <span>投资金额（万）</span>
        <input v-model.number="form.investment_wan" type="number" min="0" />
      </label>

      <label>
        <span>商业目标</span>
        <textarea
          v-model.trim="form.goal_text"
          rows="4"
          placeholder="例如：计划在泰国设厂，投资 3000 万美元，目标 14 个月试产。"
        ></textarea>
      </label>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="actions">
        <button
          v-if="auth.user?.role === 'client'"
          class="primary"
          :disabled="busy"
          @click="nextStep"
        >
          下一步：填写问卷
        </button>
        <button v-else class="primary" :disabled="busy" @click="submit">
          {{ busy ? '创建中…' : '创建项目' }}
        </button>
      </div>
    </div>

    <div v-else class="questionnaire-step">
      <div v-if="!questionnaire" class="state">正在加载问卷…</div>
      <template v-else>
        <QuestionnaireForm
          v-model="answers"
          :questionnaire="questionnaire"
          :project="projectFields"
          @complete="submitWithQuestionnaire"
        />
        <p v-if="error" class="error">{{ error }}</p>
        <button class="back" :disabled="busy" @click="step = 0">返回基本信息</button>
      </template>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import client from '../api/client'
import QuestionnaireForm from './QuestionnaireForm.vue'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  modelValue: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'created'])
const auth = useAuthStore()

const options = ref({})
const questionnaire = ref(null)
const answers = ref({})
const busy = ref(false)
const error = ref('')
const step = ref(0)

const form = reactive({
  name: '',
  client_name: '',
  country: '',
  industry: '',
  entry_mode: '',
  currency: 'USD',
  investment_wan: 3000,
  goal_text: ''
})

const projectFields = computed(() => ({
  country: form.country,
  industry: form.industry,
  entry_mode: form.entry_mode
}))

function close(value) {
  emit('update:modelValue', value)
}

async function loadOptions() {
  const response = await client.get('/config')
  options.value = response.data.data
  const first = (key) => response.data.data[key]?.[0]?.code || ''
  form.country = form.country || first('country')
  form.industry = form.industry || first('industry')
  form.entry_mode = form.entry_mode || first('entry_mode')
  form.currency = form.currency || first('currency')
}

async function loadQuestionnaire() {
  if (questionnaire.value) return
  const response = await client.get('/questionnaire')
  questionnaire.value = response.data.data
}

function validateBasics() {
  if (!form.country || !form.industry || !form.entry_mode) {
    error.value = '请选择国家、行业和出海方式。'
    return false
  }
  if (auth.user?.role !== 'client' && !form.client_name.trim()) {
    error.value = '请填写客户名称。'
    return false
  }
  error.value = ''
  return true
}

async function nextStep() {
  if (!validateBasics()) return
  busy.value = true
  try {
    await loadQuestionnaire()
    step.value = 1
  } catch (err) {
    error.value = err.response?.data?.message || '问卷加载失败'
  } finally {
    busy.value = false
  }
}

function payload(questionnaireAnswers = null) {
  const data = {
    name: form.name,
    client_name: form.client_name,
    country: form.country,
    industry: form.industry,
    entry_mode: form.entry_mode,
    currency: form.currency,
    investment_cents: Math.round(Number(form.investment_wan || 0) * 10000 * 100),
    goal_text: form.goal_text
  }
  if (questionnaireAnswers) {
    data.questionnaire = {
      id: questionnaire.value?.questionnaire_id,
      version: questionnaire.value?.version,
      answers: questionnaireAnswers
    }
  }
  return data
}

async function create(data) {
  busy.value = true
  error.value = ''
  try {
    const response = await client.post('/projects', data)
    emit('created', response.data.data)
    close(false)
  } catch (err) {
    error.value = err.response?.data?.message || '创建失败'
  } finally {
    busy.value = false
  }
}

async function submit() {
  if (!validateBasics()) return
  await create(payload())
}

async function submitWithQuestionnaire(completedAnswers) {
  if (!validateBasics()) {
    step.value = 0
    return
  }
  await create(payload(completedAnswers))
}

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    error.value = ''
    step.value = 0
    answers.value = {}
    try {
      await loadOptions()
      if (auth.user?.role === 'client') {
        await loadQuestionnaire()
      }
    } catch (err) {
      error.value = err.response?.data?.message || '配置加载失败'
    }
  }
)
</script>

<style scoped>
.steps {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 12px;
  color: var(--text-3);
}

.steps .active {
  color: var(--accent);
  font-weight: 650;
}

.line {
  width: 28px;
  height: 1px;
  background: var(--border);
}

.form {
  display: grid;
  gap: 12px;
}

label {
  display: grid;
  gap: 5px;
  font-size: 12px;
  color: var(--text-2);
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

input,
select,
textarea {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
  background: #fff;
}

input:focus,
select:focus,
textarea:focus {
  border-color: var(--accent);
}

.hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-3);
}

.error {
  margin: 6px 0 0;
  color: #dc2626;
  font-size: 12px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

.primary {
  height: 40px;
  padding: 0 20px;
  border: 0;
  border-radius: 9px;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}

.primary:disabled {
  opacity: 0.6;
}

.questionnaire-step {
  min-height: 420px;
}

.back {
  margin-top: 10px;
  border: 0;
  background: none;
  color: var(--text-3);
  font-size: 12px;
  cursor: pointer;
}

.state {
  padding: 40px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}

@media (max-width: 720px) {
  .row {
    grid-template-columns: 1fr;
  }

  .questionnaire-step {
    min-height: 0;
  }
}
</style>

<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">O</span>
        <span class="brand-name">Oversea</span>
      </div>
      <div class="topbar-right">
        <span class="status-dot" :class="healthState"></span>
        <span class="status-text">{{ healthText }}</span>
      </div>
    </header>

    <main class="hero">
      <p class="eyebrow">AI 原生专业服务总包平台 · MVP</p>
      <h1>把一次海外设厂<br />推进成一条可验收的交付链</h1>
      <p class="lede">
        客户只说目标。平台负责拆解任务、找到当地服务商、统一采购、监督交付，
        并在每个节点留下可追溯的验收记录。
      </p>

      <div class="actions">
        <router-link class="primary" to="/">进入工作台</router-link>
        <a class="ghost" href="http://127.0.0.1:5000/api/health" target="_blank" rel="noreferrer">
          查看 API 状态
        </a>
      </div>

      <section class="cards">
        <article class="card">
          <span class="card-index">01</span>
          <h3>对话诊断</h3>
          <p>一段目标、几份资料，生成事实表、追问清单与 30 项任务地图。</p>
        </article>
        <article class="card">
          <span class="card-index">02</span>
          <h3>建议书与采购</h3>
          <p>路线图、关键路径与预算区间；客户勾选服务，平台发起询价。</p>
        </article>
        <article class="card">
          <span class="card-index">03</span>
          <h3>履约与验收</h3>
          <p>节点看板、专家盲评、整改循环；通过后才解锁后续任务。</p>
        </article>
      </section>

      <footer class="footnote">
        当前为 A 项底座：数据库、种子数据与配置已就绪。登录、对话与业务流程将在 B–J 项实现。
      </footer>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import client from '../api/client'

const health = ref('checking')

const healthState = computed(() => {
  if (health.value === 'ok') return 'ok'
  if (health.value === 'down') return 'down'
  return 'checking'
})

const healthText = computed(() => {
  if (health.value === 'ok') return 'API 已连接'
  if (health.value === 'down') return 'API 未启动'
  return '正在检查 API'
})

onMounted(async () => {
  try {
    await client.get('/health')
    health.value = 'ok'
  } catch {
    health.value = 'down'
  }
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background:
    radial-gradient(1200px 500px at 70% -10%, rgba(77, 107, 254, 0.08), transparent 60%),
    var(--bg);
}

.topbar {
  height: 64px;
  padding: 0 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: #fff;
  background: var(--accent);
  font-weight: 700;
  font-size: 14px;
}

.brand-name {
  font-weight: 650;
  letter-spacing: 0.2px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-2);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-3);
}

.status-dot.ok {
  background: #22c55e;
}

.status-dot.down {
  background: #ef4444;
}

.hero {
  max-width: 1080px;
  margin: 0 auto;
  padding: 96px 48px 72px;
}

.eyebrow {
  margin: 0 0 20px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
}

h1 {
  margin: 0;
  font-size: clamp(34px, 5vw, 56px);
  line-height: 1.12;
  letter-spacing: -0.03em;
  font-weight: 680;
  color: var(--text);
}

.lede {
  max-width: 640px;
  margin: 24px 0 0;
  font-size: 16px;
  line-height: 1.8;
  color: var(--text-2);
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: 32px;
}

.primary,
.ghost {
  height: 42px;
  padding: 0 20px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: 0.15s ease;
}

.primary {
  color: #fff;
  background: var(--accent);
}

.primary:hover {
  filter: brightness(1.05);
}

.ghost {
  color: var(--text);
  border: 1px solid var(--border);
  background: #fff;
}

.ghost:hover {
  border-color: #c9ced6;
}

.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 72px;
}

.card {
  padding: 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #fff;
}

.card-index {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
}

.card h3 {
  margin: 14px 0 8px;
  font-size: 16px;
  font-weight: 650;
}

.card p {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-2);
}

.footnote {
  margin-top: 48px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-3);
}

@media (max-width: 860px) {
  .topbar {
    padding: 0 20px;
  }

  .hero {
    padding: 56px 20px;
  }

  .cards {
    grid-template-columns: 1fr;
    margin-top: 48px;
  }
}
</style>

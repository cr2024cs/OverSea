<template>
  <div ref="chartEl" class="task-chart"></div>
</template>

<script setup>
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  graph: { type: Object, default: null }
})

const chartEl = ref(null)
let chart = null
let observer = null

function buildOption() {
  const tasks = props.graph?.tasks || []
  const critical = new Set(props.graph?.critical_path || [])
  const edges = props.graph?.edges || []
  const stageOrder = [...new Set(tasks.map((task) => task.stage_no))].sort(
    (left, right) => left - right
  )
  const counters = {}
  const nodes = tasks.map((task) => {
    const row = counters[task.stage_no] || 0
    counters[task.stage_no] = row + 1
    return {
      name: task.code,
      x: stageOrder.indexOf(task.stage_no) * 160,
      y: row * 48,
      symbolSize: task.is_critical ? 30 : 24,
      itemStyle: {
        color: task.is_critical
          ? '#f59e0b'
          : task.locked
            ? '#b9c0cb'
            : '#4d6bfe'
      },
      label: {
        show: true,
        formatter: task.code,
        fontSize: 9,
        color: '#fff'
      },
      task
    }
  })

  const criticalEdges = new Set()
  const path = props.graph?.critical_path || []
  for (let index = 0; index < path.length - 1; index += 1) {
    criticalEdges.add(`${path[index]}>${path[index + 1]}`)
  }

  const links = edges.map((edge) => ({
    source: edge.source,
    target: edge.target,
    lineStyle: {
      color: criticalEdges.has(`${edge.source}>${edge.target}`)
        ? '#f59e0b'
        : '#d6dae1',
      width: criticalEdges.has(`${edge.source}>${edge.target}`) ? 2 : 1
    }
  }))

  return {
    animation: false,
    tooltip: {
      confine: true,
      formatter: (params) => {
        const task = params.data?.task
        if (!task) return params.name
        return [
          `<strong>${task.code} ${task.name}</strong>`,
          `阶段 ${task.stage_no} · ${task.status}`,
          `周期 ${task.duration_days} 天`,
          task.locked ? '未解锁' : '已解锁',
          task.is_critical ? '关键路径' : '非关键'
        ].join('<br/>')
      }
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        zoom: 0.85,
        data: nodes,
        links,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 6,
        lineStyle: { curveness: 0.05 },
        label: { position: 'inside' }
      }
    ]
  }
}

function render() {
  if (!chart) return
  chart.setOption(buildOption(), true)
}

onMounted(() => {
  chart = echarts.init(chartEl.value)
  render()
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(chartEl.value)
})

watch(() => props.graph, render, { deep: true })

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.task-chart {
  width: 100%;
  height: 320px;
  margin-bottom: 8px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fff;
}
</style>

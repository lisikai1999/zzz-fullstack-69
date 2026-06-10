<template>
  <div class="flow-trend" style="padding: 20px">
    <el-page-header @back="$router.push('/')">
      <template #content>
        <span>{{ intersection?.name }} - 流量趋势</span>
      </template>
    </el-page-header>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="6">
        <el-card>
          <template #header>检测器</template>
          <el-table :data="detectors" size="small" border highlight-current-row @current-change="onDetectorSelect">
            <el-table-column prop="detector_name" label="名称" />
            <el-table-column prop="approach" label="方向" width="60" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="18">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>流量时间序列</span>
              <el-date-picker v-model="dateRange" type="datetimerange" range-separator="至"
                start-placeholder="开始" end-placeholder="结束" size="small"
                @change="loadFlow" />
            </div>
          </template>
          <div ref="chartRef" style="height: 400px"></div>
          <el-empty v-if="!selectedDetector" description="选择检测器查看流量数据" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { getIntersection, getDetectors, getDetectorFlow } from '../api/traffic'

const route = useRoute()
const intersection = ref(null)
const detectors = ref([])
const selectedDetector = ref(null)
const dateRange = ref(null)
const chartRef = ref(null)
let chart = null

onMounted(async () => {
  const id = route.params.id
  const { data: intx } = await getIntersection(id)
  intersection.value = intx
  const { data: dets } = await getDetectors(id)
  detectors.value = dets
})

function onDetectorSelect(row) {
  selectedDetector.value = row
  loadFlow()
}

async function loadFlow() {
  if (!selectedDetector.value) return
  const params = {}
  if (dateRange.value) {
    params.start = dateRange.value[0]?.toISOString()
    params.end = dateRange.value[1]?.toISOString()
  }
  const { data } = await getDetectorFlow(selectedDetector.value.id, params.start, params.end)
  renderChart(data)
}

function renderChart(flowData) {
  if (!chartRef.value) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const timestamps = flowData.map(d => d.timestamp)
  const volumes = flowData.map(d => d.volume)
  const speeds = flowData.map(d => d.speed)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['流量 (veh)', '速度 (km/h)'] },
    xAxis: { type: 'category', data: timestamps, axisLabel: { rotate: 45 } },
    yAxis: [
      { type: 'value', name: '流量 (veh)' },
      { type: 'value', name: '速度 (km/h)' },
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [
      { name: '流量 (veh)', type: 'bar', data: volumes, itemStyle: { color: '#409eff' } },
      { name: '速度 (km/h)', type: 'line', yAxisIndex: 1, data: speeds, itemStyle: { color: '#e6a23c' } },
    ],
  })
}
</script>

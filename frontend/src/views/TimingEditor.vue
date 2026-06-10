<template>
  <div class="timing-editor" style="padding: 20px">
    <el-page-header @back="$router.push('/')">
      <template #content>
        <span>{{ intersection?.name }} - 配时优化</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="14">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>相位参数</span>
              <div>
                <el-button size="small" @click="addPhase">添加相位</el-button>
                <el-button size="small" type="success" @click="saveAll">保存</el-button>
                <el-button size="small" type="primary" @click="runWebster" :loading="optimizing">Webster优化</el-button>
              </div>
            </div>
          </template>

          <el-table :data="phases" border size="small">
            <el-table-column prop="phase_number" label="相位" width="60" />
            <el-table-column label="名称" width="120">
              <template #default="{ row }">
                <el-input v-model="row.phase_name" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="类型" width="110">
              <template #default="{ row }">
                <el-select v-model="row.phase_type" size="small" @change="onTypeChange(row)">
                  <el-option label="机动车" value="vehicle" />
                  <el-option label="行人" value="pedestrian" />
                  <el-option label="左转保护" value="left_turn" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="流量 q (veh/h)" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.flow_rate" :min="0" :max="3000" size="small" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="饱和流量 s" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.saturation_flow" :min="100" :max="3600" size="small" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="最小绿" width="90">
              <template #default="{ row }">
                <el-input-number v-model="row.min_green" :min="3" :max="60" size="small" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="最大绿" width="90">
              <template #default="{ row }">
                <el-input-number v-model="row.max_green" :min="10" :max="120" size="small" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="损失时间" width="90">
              <template #default="{ row }">
                <el-input-number v-model="row.lost_time" :min="1" :max="10" :step="0.5" size="small" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="" width="60">
              <template #default="{ $index }">
                <el-button type="danger" size="small" circle @click="removePhase($index)">
                  <span>&times;</span>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card v-if="result">
          <template #header>优化结果</template>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="最优周期">{{ result.optimal_cycle }}s</el-descriptions-item>
            <el-descriptions-item label="实际周期">{{ result.actual_cycle }}s</el-descriptions-item>
            <el-descriptions-item label="饱和度 Y">{{ result.degree_of_saturation }}</el-descriptions-item>
            <el-descriptions-item label="过饱和">
              <el-tag :type="result.is_oversaturated ? 'danger' : 'success'" size="small">
                {{ result.is_oversaturated ? '是' : '否' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <el-alert
            v-for="(w, idx) in result.warnings" :key="idx"
            :title="w" type="warning" :closable="false"
            style="margin-top: 8px"
          />

          <div ref="chartRef" style="height: 260px; margin-top: 16px"></div>
        </el-card>

        <el-card v-if="!result" style="text-align: center; padding: 40px">
          <p style="color: #909399">设置相位参数后点击"Webster优化"查看结果</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getIntersection, getPhases, savePhases, optimizeWebster } from '../api/traffic'

const route = useRoute()
const routerNav = useRouter()
const intersection = ref(null)
const phases = ref([])
const result = ref(null)
const optimizing = ref(false)
const chartRef = ref(null)
let chart = null

onMounted(async () => {
  const id = route.params.id
  const { data: intx } = await getIntersection(id)
  intersection.value = intx
  const { data: ph } = await getPhases(id)
  phases.value = ph.length > 0 ? ph : getDefaultPhases()
})

function getDefaultPhases() {
  return [
    { phase_number: 1, phase_name: '南北直行', phase_type: 'vehicle', flow_rate: 600, saturation_flow: 1800, min_green: 7, max_green: 60, lost_time: 3, yellow_time: 3, all_red_time: 2 },
    { phase_number: 2, phase_name: '南北左转', phase_type: 'left_turn', flow_rate: 200, saturation_flow: 1600, min_green: 5, max_green: 40, lost_time: 3, yellow_time: 3, all_red_time: 2 },
    { phase_number: 3, phase_name: '东西直行', phase_type: 'vehicle', flow_rate: 500, saturation_flow: 1800, min_green: 7, max_green: 60, lost_time: 3, yellow_time: 3, all_red_time: 2 },
    { phase_number: 4, phase_name: '行人过街', phase_type: 'pedestrian', flow_rate: 100, saturation_flow: 1200, min_green: 15, max_green: 40, lost_time: 3, yellow_time: 3, all_red_time: 2 },
  ]
}

function addPhase() {
  const next = phases.value.length > 0 ? Math.max(...phases.value.map(p => p.phase_number)) + 1 : 1
  phases.value.push({
    phase_number: next, phase_name: '', phase_type: 'vehicle',
    flow_rate: 400, saturation_flow: 1800, min_green: 7, max_green: 60,
    lost_time: 3, yellow_time: 3, all_red_time: 2,
  })
}

function removePhase(index) {
  phases.value.splice(index, 1)
}

function onTypeChange(row) {
  if (row.phase_type === 'pedestrian') {
    row.min_green = 15
    row.saturation_flow = 1200
  } else if (row.phase_type === 'left_turn') {
    row.min_green = 5
    row.saturation_flow = 1600
  } else {
    row.min_green = 7
    row.saturation_flow = 1800
  }
}

async function saveAll() {
  try {
    await savePhases(route.params.id, phases.value)
    ElMessage.success('相位数据已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function runWebster() {
  optimizing.value = true
  try {
    await savePhases(route.params.id, phases.value)
    const { data } = await optimizeWebster(route.params.id)
    result.value = data
    await nextTick()
    renderChart(data)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '优化失败')
  } finally {
    optimizing.value = false
  }
}

function renderChart(data) {
  if (!chartRef.value) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const phaseNames = data.phases.map(p => `相位${p.phase_number}`)
  const greenTimes = data.phases.map(p => p.green_time)
  const flowRatios = data.phases.map(p => p.flow_ratio)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['绿灯时间(s)', '流量比'] },
    xAxis: { type: 'category', data: phaseNames },
    yAxis: [
      { type: 'value', name: '绿灯时间(s)' },
      { type: 'value', name: '流量比', max: 1 },
    ],
    series: [
      { name: '绿灯时间(s)', type: 'bar', data: greenTimes, itemStyle: { color: '#67c23a' } },
      { name: '流量比', type: 'line', yAxisIndex: 1, data: flowRatios, itemStyle: { color: '#e6a23c' } },
    ],
  })
}
</script>

<style scoped>
.timing-editor {
  height: 100%;
  overflow-y: auto;
}
</style>

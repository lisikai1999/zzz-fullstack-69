<template>
  <div class="time-space" style="padding: 20px">
    <el-page-header @back="$router.push('/arterials')">
      <template #content>
        <span>{{ arterial?.name }} - 绿波时空图</span>
      </template>
      <template #extra>
        <el-button type="primary" @click="runOptimize" :loading="loading">计算绿波</el-button>
      </template>
    </el-page-header>

    <el-row :gutter="16" style="margin-top: 16px" v-if="diagramData">
      <el-col :span="6">
        <el-card>
          <template #header>参数</template>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="设计速度">{{ arterial?.design_speed }} km/h</el-descriptions-item>
            <el-descriptions-item label="公共周期">{{ diagramData.common_cycle }}s</el-descriptions-item>
            <el-descriptions-item label="带宽">{{ diagramData.bandwidth }}s</el-descriptions-item>
            <el-descriptions-item label="绿波效率">{{ diagramData.efficiency }}%</el-descriptions-item>
          </el-descriptions>

          <h4 style="margin-top: 16px; margin-bottom: 8px">路口偏移</h4>
          <el-table :data="diagramData.offsets" size="small" border>
            <el-table-column prop="distance" label="距离(m)" width="80" />
            <el-table-column prop="offset" label="偏移(s)" width="80" />
            <el-table-column prop="green_time" label="绿灯(s)" width="80" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="18">
        <el-card>
          <template #header>时空图</template>
          <div ref="chartRef" style="height: 500px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!diagramData && !loading" description="点击【计算绿波】生成时空图" />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getArterial, optimizeGreenwave } from '../api/traffic'

const route = useRoute()
const arterial = ref(null)
const diagramData = ref(null)
const loading = ref(false)
const chartRef = ref(null)
let chart = null

onMounted(async () => {
  const { data } = await getArterial(route.params.id)
  arterial.value = data
})

async function runOptimize() {
  loading.value = true
  try {
    const { data } = await optimizeGreenwave(route.params.id)
    diagramData.value = data
    await nextTick()
    renderTimeSpaceDiagram(data)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '计算失败')
  } finally {
    loading.value = false
  }
}

function renderTimeSpaceDiagram(data) {
  if (!chartRef.value) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const maxDist = Math.max(...data.offsets.map(o => o.distance))
  const totalTime = data.common_cycle * 3

  // Compute the max y needed for speed lines and band polygons
  const speedLineMaxY = (2 * data.common_cycle) + maxDist / data.design_speed_mps
  const bandMaxY = data.band_polygons.length > 0
    ? Math.max(...data.band_polygons.flatMap(bp => bp.lower.map(p => p.y)))
    : totalTime
  const yAxisMax = Math.max(totalTime, speedLineMaxY, bandMaxY)

  // Green rectangles: each item is [distance, green_start, green_end]
  // renderItem uses all three dimensions from the data array
  const greenSeriesData = data.time_space_data.map(item => [
    item.distance,
    item.green_start,
    item.green_end,
  ])

  const greenSeries = {
    name: '绿灯窗口',
    type: 'custom',
    renderItem: (params, api) => {
      // api.value(dim) reads from the data item at params.dataIndex
      const distance = api.value(0)
      const greenStart = api.value(1)
      const greenEnd = api.value(2)

      // Convert data coords to pixel coords
      const topLeft = api.coord([distance, greenEnd])
      const bottomRight = api.coord([distance, greenStart])
      const barWidth = Math.max(12, api.size([maxDist * 0.02, 0])[0])

      const height = bottomRight[1] - topLeft[1]
      if (height <= 0) return null

      return {
        type: 'rect',
        shape: {
          x: topLeft[0] - barWidth / 2,
          y: topLeft[1],
          width: barWidth,
          height: height,
        },
        style: {
          fill: 'rgba(103, 194, 58, 0.7)',
          stroke: '#4caf50',
          lineWidth: 1,
        },
      }
    },
    data: greenSeriesData,
    encode: { x: 0, y: [1, 2] },
    z: 10,
  }

  // Band polygons: one custom series per band, each with a single data point
  // to trigger exactly one renderItem call that draws the full polygon.
  // Data includes the band's bounding box values so api.coord() maps correctly.
  const bandSeries = data.band_polygons.map((band, idx) => {
    // Compute bounding box of this polygon for axis reference
    const allX = [...band.upper.map(p => p.x), ...band.lower.map(p => p.x)]
    const allY = [...band.upper.map(p => p.y), ...band.lower.map(p => p.y)]
    const minX = Math.min(...allX)
    const maxX = Math.max(...allX)
    const minY = Math.min(...allY)
    const maxY = Math.max(...allY)

    return {
      name: idx === 0 ? '绿波带' : '',
      type: 'custom',
      renderItem: (params, api) => {
        if (params.dataIndex !== 0) return null
        // Use closure-captured `band` data to build polygon points
        const upperPixels = band.upper.map(p => api.coord([p.x, p.y]))
        const lowerPixels = band.lower.map(p => api.coord([p.x, p.y]))
        // Polygon: upper left→right, then lower right→left (closed shape)
        const points = [...upperPixels, ...[...lowerPixels].reverse()]
        return {
          type: 'polygon',
          shape: { points },
          style: {
            fill: 'rgba(64, 158, 255, 0.15)',
            stroke: 'rgba(64, 158, 255, 0.7)',
            lineWidth: 1.5,
          },
        }
      },
      // Include bounding-box corners so ECharts axis auto-range includes these points.
      // Only the first item triggers the polygon render (dataIndex === 0 check above).
      data: [[minX, minY], [maxX, maxY]],
      z: 5,
      silent: true,
    }
  })

  // Speed lines as markLine on the green series (uses coord format correctly)
  const speedMarkLines = []
  for (let k = 0; k < 3; k++) {
    const startTime = k * data.common_cycle
    const endTime = startTime + maxDist / data.design_speed_mps
    speedMarkLines.push([
      { coord: [0, startTime] },
      { coord: [maxDist, endTime] },
    ])
  }

  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.seriesName === '绿灯窗口' && params.data) {
          return `距离: ${params.data[0]}m<br/>绿灯: ${params.data[1].toFixed(1)}s ~ ${params.data[2].toFixed(1)}s`
        }
        return params.seriesName
      }
    },
    grid: { left: 70, right: 40, top: 40, bottom: 60 },
    xAxis: {
      type: 'value',
      name: '距离 (m)',
      min: 0,
      max: maxDist,
      nameLocation: 'middle',
      nameGap: 35,
    },
    yAxis: {
      type: 'value',
      name: '时间 (s)',
      min: 0,
      max: yAxisMax,
      nameLocation: 'middle',
      nameGap: 45,
    },
    series: [
      {
        ...greenSeries,
        markLine: {
          symbol: 'none',
          lineStyle: { color: '#f56c6c', width: 1.5, type: 'dashed' },
          label: { show: false },
          data: speedMarkLines,
        },
      },
      ...bandSeries,
    ],
  })
}
</script>

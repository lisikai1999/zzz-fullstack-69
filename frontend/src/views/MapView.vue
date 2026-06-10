<template>
  <div class="map-container">
    <div id="map" ref="mapRef" class="map"></div>
    <el-card class="map-sidebar" v-if="selectedIntersection">
      <template #header>
        <div class="sidebar-header">
          <span>{{ selectedIntersection.name }}</span>
          <el-button type="primary" size="small" @click="goToTiming">配时编辑</el-button>
        </div>
      </template>
      <el-descriptions :column="1" size="small">
        <el-descriptions-item label="类型">{{ selectedIntersection.intersection_type }}</el-descriptions-item>
        <el-descriptions-item label="总损失时间">{{ selectedIntersection.total_lost_time }}s</el-descriptions-item>
        <el-descriptions-item label="周期范围">{{ selectedIntersection.min_cycle }}-{{ selectedIntersection.max_cycle }}s</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 12px">
        <el-button size="small" @click="goToFlow">流量趋势</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { getIntersections } from '../api/traffic'

const router = useRouter()
const mapRef = ref(null)
const selectedIntersection = ref(null)
let map = null
let markers = []

const intersections = ref([])

onMounted(async () => {
  map = L.map('map').setView([30.57, 104.07], 14)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map)

  await loadIntersections()
})

onUnmounted(() => {
  if (map) map.remove()
})

async function loadIntersections() {
  const { data } = await getIntersections()
  intersections.value = data
  markers.forEach(m => map.removeLayer(m))
  markers = []

  data.forEach(intx => {
    const marker = L.circleMarker([intx.latitude, intx.longitude], {
      radius: 10,
      color: '#409eff',
      fillColor: '#409eff',
      fillOpacity: 0.6,
      weight: 2,
    }).addTo(map)

    marker.bindTooltip(intx.name)
    marker.on('click', () => {
      selectedIntersection.value = intx
    })
    markers.push(marker)
  })

  if (data.length > 0) {
    const bounds = L.latLngBounds(data.map(i => [i.latitude, i.longitude]))
    map.fitBounds(bounds, { padding: [50, 50] })
  }
}

function goToTiming() {
  router.push(`/timing/${selectedIntersection.value.id}`)
}

function goToFlow() {
  router.push(`/flow/${selectedIntersection.value.id}`)
}
</script>

<style scoped>
.map-container {
  position: relative;
  height: 100%;
  width: 100%;
}

.map {
  height: 100%;
  width: 100%;
}

.map-sidebar {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 320px;
  z-index: 1000;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

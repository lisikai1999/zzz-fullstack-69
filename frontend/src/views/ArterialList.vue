<template>
  <div class="arterial-list" style="padding: 20px">
    <el-row :gutter="20">
      <el-col :span="24">
        <h2>干线绿波协调</h2>
        <el-table :data="arterials" stripe @row-click="goToArterial" style="cursor: pointer; margin-top: 16px">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="干线名称" />
          <el-table-column prop="design_speed" label="设计速度 (km/h)" width="150" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click.stop="goToArterial(row)">绿波图</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getArterials } from '../api/traffic'

const router = useRouter()
const arterials = ref([])

onMounted(async () => {
  const { data } = await getArterials()
  arterials.value = data
})

function goToArterial(row) {
  router.push(`/arterial/${row.id}`)
}
</script>

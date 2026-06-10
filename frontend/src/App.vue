<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <h1>交通信号配时优化系统</h1>
      <el-menu mode="horizontal" :router="true" :default-active="$route.path">
        <el-menu-item index="/">地图总览</el-menu-item>
        <el-menu-item index="/arterials">绿波协调</el-menu-item>
      </el-menu>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
</script>

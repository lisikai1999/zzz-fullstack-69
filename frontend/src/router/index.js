import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'map', component: () => import('../views/MapView.vue') },
  { path: '/timing/:id', name: 'timing', component: () => import('../views/TimingEditor.vue') },
  { path: '/arterials', name: 'arterials', component: () => import('../views/ArterialList.vue') },
  { path: '/arterial/:id', name: 'arterial', component: () => import('../views/TimeSpaceDiagram.vue') },
  { path: '/flow/:id', name: 'flow', component: () => import('../views/FlowTrend.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})

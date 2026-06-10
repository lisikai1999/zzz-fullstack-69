import api from './index'

export const getIntersections = () => api.get('/intersections')
export const getIntersection = (id) => api.get(`/intersections/${id}`)
export const createIntersection = (data) => api.post('/intersections', data)
export const updateIntersection = (id, data) => api.put(`/intersections/${id}`, data)
export const deleteIntersection = (id) => api.delete(`/intersections/${id}`)

export const getPhases = (intersectionId) => api.get(`/intersections/${intersectionId}/phases`)
export const savePhases = (intersectionId, phases) => api.post(`/intersections/${intersectionId}/phases`, { phases })

export const optimizeWebster = (intersectionId) => api.post(`/optimize/webster/${intersectionId}`)
export const optimizeGreenwave = (arterialId) => api.post(`/optimize/greenwave/${arterialId}`)
export const getGreenwaveDiagram = (arterialId) => api.get(`/optimize/greenwave/${arterialId}/diagram`)
export const optimizeAdaptive = (intersectionId, mode = 'scoot') => api.post(`/optimize/adaptive/${intersectionId}`, { mode })

export const getArterials = () => api.get('/arterials')
export const getArterial = (id) => api.get(`/arterials/${id}`)
export const createArterial = (data) => api.post('/arterials', data)

export const getDetectorFlow = (detectorId, start, end) => api.get(`/detectors/${detectorId}/flow`, { params: { start, end } })
export const getDetectors = (intersectionId) => api.get(`/intersections/${intersectionId}/detectors`)

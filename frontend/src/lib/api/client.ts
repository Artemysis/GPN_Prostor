import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

export const http = axios.create({
  baseURL: API_URL,
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('prostor.token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — inject JWT on every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor — on 401, token is invalid/expired, force logout
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      // Dispatch a custom event so AuthContext can react without a direct import cycle
      window.dispatchEvent(new Event('auth:logout'))
    }
    return Promise.reject(error)
  }
)

export default client
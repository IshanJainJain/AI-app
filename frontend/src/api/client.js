import axios from 'axios'

const client = axios.create({
  baseURL: '/',
})

// Attach token to every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Redirect to login on 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const requestUrl = error.config?.url || ''
    const isAuthRequest = requestUrl.startsWith('/auth/')

    if (status === 401 && !isAuthRequest) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }

    return Promise.reject(error)
  }
)

export default client
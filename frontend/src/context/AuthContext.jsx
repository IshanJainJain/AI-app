import { createContext, useContext, useEffect, useState } from 'react'
import client from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }
    // Validate token on app load
    client.get('/users/me')
      .then((res) => setUser(res.data))
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false))
  }, [])

  const login = async (loginId, password) => {
    const res = await client.post('/auth/login', { login: loginId, password })
    localStorage.setItem('token', res.data.access_token)
    const me = await client.get('/users/me')
    setUser(me.data)
  }

  const register = async (email, username, password) => {
    const res = await client.post('/auth/register', { email, username, password })
    localStorage.setItem('token', res.data.access_token)
    const me = await client.get('/users/me')
    setUser(me.data)
  }

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
    window.location.href = '/login'
  }

  const handleOAuthCallback = (token) => {
    localStorage.setItem('token', token)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, handleOAuthCallback }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
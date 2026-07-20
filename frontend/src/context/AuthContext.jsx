import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import client from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('auth_token'))
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const isAuthenticated = Boolean(token)

  // Listen for 401s from axios interceptor — force logout on expired/invalid token
  useEffect(() => {
    const handleForceLogout = () => {
      setToken(null)
      setUser(null)
    }
    window.addEventListener('auth:logout', handleForceLogout)
    return () => window.removeEventListener('auth:logout', handleForceLogout)
  }, [])

  const register = useCallback(async (email, password) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await client.post('/auth/register', { email, password })
      const { access_token } = res.data
      localStorage.setItem('auth_token', access_token)
      setToken(access_token)
    } catch (err) {
      const message = err.response?.data?.message || 'Registration failed.'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const login = useCallback(async (email, password) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await client.post('/auth/login', { email, password })
      const { access_token } = res.data
      localStorage.setItem('auth_token', access_token)
      setToken(access_token)
    } catch (err) {
      const message = err.response?.data?.message || 'Invalid email or password.'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token')
    setToken(null)
    setUser(null)
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return (
    <AuthContext.Provider value={{
      token,
      user,
      isAuthenticated,
      isLoading,
      error,
      login,
      register,
      logout,
      clearError,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
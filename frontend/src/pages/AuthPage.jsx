import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function AuthPage() {
  const { login, register, isLoading, error, clearError } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const isLogin = mode === 'login'

  const handleSubmit = async (e) => {
    e.preventDefault()
    clearError()
    try {
      if (isLogin) {
        await login(email, password)
      } else {
        await register(email, password)
      }
    } catch {
      // error is set in AuthContext — displayed below
    }
  }

  const switchMode = () => {
    clearError()
    setEmail('')
    setPassword('')
    setMode(isLogin ? 'register' : 'login')
  }

  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Logo / wordmark */}
        <div className="mb-8 text-center">
          <span className="text-2xl font-semibold tracking-tight text-gray-900">
            AgentLens
          </span>
          <p className="mt-1 text-sm text-gray-500">
            {isLogin ? 'Sign in to continue' : 'Create an account'}
          </p>
        </div>

        {/* Card */}
        <div className="border border-gray-200 rounded-xl p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg outline-none
                           focus:border-gray-500 focus:ring-1 focus:ring-gray-500
                           placeholder:text-gray-400 transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                type="password"
                required
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isLogin ? '········' : 'At least 8 characters'}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg outline-none
                           focus:border-gray-500 focus:ring-1 focus:ring-gray-500
                           placeholder:text-gray-400 transition"
              />
            </div>

            {/* Inline error */}
            {error && (
              <p className="text-sm text-red-600">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2 px-4 text-sm font-medium text-white bg-gray-900
                         rounded-lg hover:bg-gray-700 disabled:opacity-50
                         disabled:cursor-not-allowed transition"
            >
              {isLoading
                ? isLogin ? 'Signing in…' : 'Creating account…'
                : isLogin ? 'Sign in' : 'Create account'
              }
            </button>

          </form>
        </div>

        {/* Mode toggle */}
        <p className="mt-4 text-center text-sm text-gray-500">
          {isLogin ? "Don't have an account?" : 'Already have an account?'}{' '}
          <button
            onClick={switchMode}
            className="text-gray-900 font-medium hover:underline"
          >
            {isLogin ? 'Sign up' : 'Sign in'}
          </button>
        </p>

      </div>
    </div>
  )
}
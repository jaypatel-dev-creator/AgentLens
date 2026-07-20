import { AuthProvider, useAuth } from './context/AuthContext'
import { ChatProvider } from './context/ChatContext'
import AuthPage from './pages/AuthPage'
import ChatPage from './pages/ChatPage'

function AppContent() {
  const { isAuthenticated, token } = useAuth()

  if (!isAuthenticated) {
    return <AuthPage />
  }

  // key={token} forces ChatProvider to fully unmount and remount on user change.
  // This clears all thread/message/profile state so user 2 never sees user 1's data.
  return (
    <ChatProvider key={token}>
      <ChatPage />
    </ChatProvider>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
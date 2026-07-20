import { useEffect } from 'react'
import Sidebar from '../components/Sidebar/Sidebar'
import ChatWindow from '../components/Chat/ChatWindow'
import ProfileViewer from '../components/Memory/ProfileViewer'
import { useChat } from '../context/ChatContext'

export default function ChatPage() {
  const { loadThreads, showProfile } = useChat()

  useEffect(() => {
    loadThreads()
  }, [loadThreads])

  return (
    <div className="flex h-screen bg-white overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <ChatWindow />
      </main>
      {showProfile && <ProfileViewer />}
    </div>
  )
}
import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'
import client from '../api/client'

const ChatContext = createContext(null)

const MEMORY_UPDATE_PREFIX = 'MEMORY_UPDATE:'

function stripMemoryUpdates(text) {
  if (!text) return text
  return text
    .split('\n')
    .filter((line) => !line.trim().startsWith(MEMORY_UPDATE_PREFIX))
    .join('\n')
    .trim()
}

export function ChatProvider({ children }) {
  const [threads, setThreads] = useState([])
  const [activeThreadId, setActiveThreadId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingMessage, setStreamingMessage] = useState(null)
  const [profile, setProfile] = useState([])
  const [showProfile, setShowProfile] = useState(false)
  const [memoryNotification, setMemoryNotification] = useState(null)

  // --- RAG document state ---
  const [documents, setDocuments] = useState([])
  const [showDocuments, setShowDocuments] = useState(false)
  const [uploadStatuses, setUploadStatuses] = useState([])

  // --- Observability state ---
  const [sessionMetrics, setSessionMetrics] = useState(null)
  const [showObservability, setShowObservability] = useState(false)

  const doneCommittedRef = useRef(false)
  const showProfileRef = useRef(false)
  const memoryTimerRef = useRef(null)
  const activeThreadIdRef = useRef(null)   // fix: ref to avoid stale closure in handleSSEEvent
  const metricsPollerRef = useRef(null)    // holds the setInterval id for metrics polling

  showProfileRef.current = showProfile
  activeThreadIdRef.current = activeThreadId  // always current, no closure staleness

  // --- Session metrics ---

  const fetchSessionMetrics = useCallback(async (threadId) => {
    if (!threadId) return
    try {
      const res = await client.get(`/metrics/session/${threadId}`)
      setSessionMetrics(res.data)
    } catch (err) {
      // 404 means no metrics yet (stream not started or TTL expired) — not an error
      if (err.response?.status !== 404) {
        console.error('Failed to fetch session metrics:', err)
      }
    }
  }, [])

  // Start polling every 2s when stream begins, stop and do one final fetch when done
  const startMetricsPolling = useCallback((threadId) => {
    stopMetricsPolling()
    metricsPollerRef.current = setInterval(() => {
      fetchSessionMetrics(threadId)
    }, 2000)
  }, [fetchSessionMetrics])

  const stopMetricsPolling = useCallback(() => {
    if (metricsPollerRef.current) {
      clearInterval(metricsPollerRef.current)
      metricsPollerRef.current = null
    }
  }, [])

  // Clear metrics when switching threads
  useEffect(() => {
    setSessionMetrics(null)
  }, [activeThreadId])

  // Cleanup poller on unmount
  useEffect(() => {
    return () => stopMetricsPolling()
  }, [stopMetricsPolling])

  // --- Thread actions ---

  const loadThreads = useCallback(async () => {
    try {
      const res = await client.get('/threads')
      setThreads(res.data)
    } catch (err) {
      console.error('Failed to load threads:', err)
    }
  }, [])

  const createThread = useCallback(async () => {
    try {
      const res = await client.post('/threads', { title: 'New Chat' })
      setThreads((prev) => [res.data, ...prev])
      setActiveThreadId(res.data.id)
      setMessages([])
      return res.data
    } catch (err) {
      console.error('Failed to create thread:', err)
    }
  }, [])

  const selectThread = useCallback(async (threadId) => {
    setActiveThreadId(threadId)
    setMessages([])
    setStreamingMessage(null)
    try {
      const res = await client.get(`/chat/history/${threadId}`)
      setMessages(res.data.messages || [])
    } catch (err) {
      console.error('Failed to load history:', err)
    }
    // Fetch metrics for the selected thread — may return 404 if expired, that's fine
    fetchSessionMetrics(threadId)
  }, [fetchSessionMetrics])

  const renameThread = useCallback(async (threadId, title) => {
    try {
      await client.patch(`/threads/${threadId}`, { title })
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? { ...t, title, is_titled: true } : t))
      )
    } catch (err) {
      console.error('Failed to rename thread:', err)
    }
  }, [])

  const deleteThread = useCallback(async (threadId) => {
    try {
      await client.delete(`/threads/${threadId}`)
      setThreads((prev) => prev.filter((t) => t.id !== threadId))
      if (activeThreadId === threadId) {
        setActiveThreadId(null)
        setMessages([])
      }
    } catch (err) {
      console.error('Failed to delete thread:', err)
    }
  }, [activeThreadId])

  // --- Chat actions ---

  const sendMessage = useCallback(async (message) => {
    if (!activeThreadId || !message.trim()) return

    const humanMsg = { role: 'human', content: message }
    setMessages((prev) => [...prev, humanMsg])
    setIsStreaming(true)
    doneCommittedRef.current = false
    setStreamingMessage({
      role: 'ai',
      content: '',
      toolCalls: [],
      currentTool: null,
    })

    // Start polling metrics as soon as the stream begins
    startMetricsPolling(activeThreadId)

    try {
      // fetch() bypasses the axios interceptor — inject token manually
      const token = localStorage.getItem('auth_token')
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ thread_id: activeThreadId, message }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            handleSSEEvent(event)
          } catch {
            // skip malformed lines
          }
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
      setStreamingMessage(null)
      setIsStreaming(false)
      stopMetricsPolling()
    }
  }, [activeThreadId, startMetricsPolling, stopMetricsPolling])

  const handleSSEEvent = useCallback((event) => {
    switch (event.type) {
      case 'text':
        setStreamingMessage((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            content: stripMemoryUpdates(prev.content + event.content),
          }
        })
        break

      case 'tool_start':
        setStreamingMessage((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            currentTool: {
              tool_name: event.tool_name,
              tool_input: event.tool_input,
              tool_output: null,
              sources: [],
              status: 'running',
            },
          }
        })
        break

      case 'tool_end':
        setStreamingMessage((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            toolCalls: [
              ...prev.toolCalls,
              {
                tool_name: event.tool_name,
                tool_input: prev.currentTool?.tool_input || {},
                tool_output: event.tool_output,
                sources: event.sources || [],
                status: 'done',
              },
            ],
            currentTool: null,
          }
        })
        break

      case 'memory_update':
        if (memoryTimerRef.current) clearTimeout(memoryTimerRef.current)
        setMemoryNotification({ keys: event.keys })
        memoryTimerRef.current = setTimeout(() => {
          setMemoryNotification(null)
        }, 4000)
        if (showProfileRef.current) {
          loadProfile()
        }
        break

      case 'done':
        if (doneCommittedRef.current) break
        doneCommittedRef.current = true

        setStreamingMessage((prev) => {
          if (prev) {
            const cleanContent = stripMemoryUpdates(prev.content)
            setMessages((msgs) => {
              const last = msgs[msgs.length - 1]
              if (last && last.role === 'ai' && last.content === cleanContent) {
                return msgs
              }
              return [...msgs, { ...prev, content: cleanContent, currentTool: null }]
            })
          }
          return null
        })
        setIsStreaming(false)
        refreshThreadTitle(activeThreadIdRef.current)  // fix: use ref, not stale closure value

        // Stop polling and do one final fetch to get complete metrics
        stopMetricsPolling()
        fetchSessionMetrics(activeThreadIdRef.current)

        if (showProfileRef.current) {
          loadProfile()
        }
        break

      case 'error':
        setStreamingMessage((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            content: prev.content || 'Something went wrong. Please try again.',
          }
        })
        setIsStreaming(false)
        stopMetricsPolling()
        break

      default:
        break
    }
  }, [fetchSessionMetrics, stopMetricsPolling])

  const refreshThreadTitle = useCallback(async (threadId) => {
    if (!threadId) return
    try {
      const res = await client.get(`/threads/${threadId}`)
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? res.data : t))
      )
    } catch {
      // non-critical
    }
  }, [])

  // --- Profile actions ---

  const loadProfile = useCallback(async () => {
    try {
      const res = await client.get('/memory/profile')
      setProfile(res.data.entries || [])
    } catch (err) {
      console.error('Failed to load profile:', err)
    }
  }, [])

  const deleteProfileEntry = useCallback(async (key) => {
    try {
      await client.delete(`/memory/profile/${key}`)
      setProfile((prev) => prev.filter((e) => e.key !== key))
    } catch (err) {
      console.error('Failed to delete profile entry:', err)
    }
  }, [])

  const clearProfile = useCallback(async () => {
    try {
      await client.delete('/memory/profile')
      setProfile([])
    } catch (err) {
      console.error('Failed to clear profile:', err)
    }
  }, [])

  // --- Document actions ---

  const loadDocuments = useCallback(async () => {
    try {
      const res = await client.get('/documents/')
      setDocuments(res.data)
    } catch (err) {
      console.error('Failed to load documents:', err)
    }
  }, [])

  const uploadDocuments = useCallback(async (files) => {
    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }

    const initial = Array.from(files).map((f) => ({
      filename: f.name,
      status: 'uploading',
      message: '',
    }))
    setUploadStatuses(initial)

    try {
      const res = await client.post('/documents/upload', formData, {
        headers: { 'Content-Type': undefined },
      })

      const updated = res.data.map((r) => ({
        filename: r.filename,
        status: r.already_existed ? 'duplicate' : 'success',
        message: r.message,
      }))
      setUploadStatuses(updated)

      await loadDocuments()

      setTimeout(() => setUploadStatuses([]), 5000)
    } catch (err) {
      console.error('Upload failed:', err)
      const errored = Array.from(files).map((f) => ({
        filename: f.name,
        status: 'error',
        message: `${f.name} failed to upload`,
      }))
      setUploadStatuses(errored)
      setTimeout(() => setUploadStatuses([]), 5000)
    }
  }, [loadDocuments])

  const deleteDocument = useCallback(async (sha256) => {
    try {
      await client.delete(`/documents/${sha256}`)
      setDocuments((prev) => prev.filter((d) => d.sha256 !== sha256))
    } catch (err) {
      console.error('Failed to delete document:', err)
    }
  }, [])

  const handleToggleDocuments = useCallback(async () => {
    if (!showDocuments) await loadDocuments()
    setShowDocuments((prev) => !prev)
  }, [showDocuments, loadDocuments])

  return (
    <ChatContext.Provider value={{
      threads,
      activeThreadId,
      messages,
      isStreaming,
      streamingMessage,
      profile,
      showProfile,
      memoryNotification,
      documents,
      showDocuments,
      uploadStatuses,
      sessionMetrics,
      showObservability,
      loadThreads,
      createThread,
      selectThread,
      renameThread,
      deleteThread,
      sendMessage,
      loadProfile,
      deleteProfileEntry,
      clearProfile,
      setShowProfile,
      loadDocuments,
      uploadDocuments,
      deleteDocument,
      handleToggleDocuments,
      setShowObservability,
      fetchSessionMetrics,
    }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within ChatProvider')
  return ctx
}
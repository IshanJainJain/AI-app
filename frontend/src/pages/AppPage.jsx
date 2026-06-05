// frontend/src/pages/AppPage.jsx
import { useEffect, useState } from 'react'
import client from '../api/client'
import { useAuth } from '../context/AuthContext'
import Sidebar from '../components/Sidebar'
import Workspace from '../components/Workspace'
import styles from './AppPage.module.css'

export default function AppPage() {
  const { user, logout } = useAuth()
  const [activeThreadId, setActiveThreadId] = useState(null)
  const [threads, setThreads] = useState([])
  const [messages, setMessages] = useState([])
  const [globalContext, setGlobalContext] = useState('')
  const [imageContexts, setImageContexts] = useState([])
  const [activeThread, setActiveThread] = useState(null)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('')

  const applyPayload = (data) => {
    if (data.threads) setThreads(data.threads)
    if (data.messages) setMessages(data.messages)
    if (data.globalContext !== undefined) setGlobalContext(data.globalContext || '')
    if (data.imageContexts) setImageContexts(data.imageContexts)
    if (data.thread) {
      setActiveThread(data.thread)
      setActiveThreadId(data.thread.id)
    }
  }

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [threadsRes, contextRes] = await Promise.all([
          client.get('/api/threads'),
          client.get('/api/global-context'),
        ])

        const list = threadsRes.data.threads || []
        setThreads(list)
        setGlobalContext(contextRes.data.context || '')

        if (list.length) {
          const first = list[0]
          const threadRes = await client.get(`/api/threads/${first.id}`)
          applyPayload(threadRes.data)
        }
      } catch {
        setStatus('Could not load conversations.')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  const createThread = async () => {
    setStatus('')
    const res = await client.post('/api/threads', { title: 'New conversation' })
    applyPayload(res.data)
  }

  const selectThread = async (id) => {
    if (id === activeThreadId) return
    setStatus('')
    const res = await client.get(`/api/threads/${id}`)
    applyPayload(res.data)
  }

  const deleteThread = async (id) => {
    const res = await client.delete(`/api/threads/${id}`)
    applyPayload(res.data)
    if (!res.data.thread) {
      setActiveThread(null)
      setActiveThreadId(null)
      setMessages([])
      setImageContexts([])
    }
  }

  const renameThread = async (title) => {
    if (!activeThreadId || !title.trim()) return
    const res = await client.patch(`/api/threads/${activeThreadId}`, { title: title.trim() })
    applyPayload(res.data)
    setStatus('Saved.')
  }

  const sendPrompt = async (prompt) => {
    if (!activeThreadId || !prompt.trim()) return
    setStatus('Sending...')
    try {
      const optimistic = {
        id: `local-${Date.now()}`,
        role: 'user',
        content: prompt,
        created_at: new Date().toISOString(),
      }
      setMessages((current) => [...current, optimistic])

      const res = await client.post(`/api/threads/${activeThreadId}/prompt`, { prompt })
      applyPayload(res.data)
      setStatus('Saved.')
    } catch {
      setStatus('Could not send message.')
    }
  }

  const saveGlobalContext = async () => {
    const res = await client.put('/api/global-context', { context: globalContext })
    setGlobalContext(res.data.context || '')
  }

  const clearGlobalContext = async () => {
    const res = await client.delete('/api/global-context')
    setGlobalContext(res.data.context || '')
  }

  const addImageContext = async ({ filename, imageBase64, prompt }) => {
    if (!activeThreadId) return
    const res = await client.post(`/api/threads/${activeThreadId}/image-contexts`, {
      filename,
      image: imageBase64,
      prompt,
    })
    setImageContexts(res.data.imageContexts || [])
}

  const deleteImageContext = async (ctxId) => {
    if (!activeThreadId) return
    const res = await client.delete(`/api/threads/${activeThreadId}/image-contexts/${ctxId}`)
    setImageContexts(res.data.imageContexts || [])
  }

  return (
    <div className={styles.appShell}>
      <Sidebar
        user={user}
        threads={threads}
        activeThreadId={activeThreadId}
        globalContext={globalContext}
        imageContexts={imageContexts}
        onGlobalContextChange={setGlobalContext}
        onSaveGlobalContext={saveGlobalContext}
        onClearGlobalContext={clearGlobalContext}
        onCreateThread={createThread}
        onSelectThread={selectThread}
        onDeleteThread={deleteThread}
        onAddImageContext={addImageContext}
        onDeleteImageContext={deleteImageContext}
        onLogout={logout}
      />
      <Workspace
        loading={loading}
        thread={activeThread}
        messages={messages}
        status={status}
        onRenameThread={renameThread}
        onSendPrompt={sendPrompt}
      />
    </div>
  )
}
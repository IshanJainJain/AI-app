// frontend/src/components/Workspace.jsx
import { useEffect, useRef, useState } from 'react'
import styles from './Workspace.module.css'

function formatTime(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}

export default function Workspace({ loading, thread, messages, status, onRenameThread, onSendPrompt }) {
  const [title, setTitle] = useState('')
  const [prompt, setPrompt] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    setTitle(thread?.title || '')
  }, [thread])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!prompt.trim() || sending) return
    const value = prompt
    setPrompt('')
    setSending(true)
    await onSendPrompt(value)
    setSending(false)
  }

  const rename = (e) => {
    e.preventDefault()
    onRenameThread(title)
  }

  return (
    <main className={styles.workspace}>
      <header className={styles.topbar}>
        <form onSubmit={rename} className={styles.renameForm}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Untitled conversation"
            disabled={!thread}
          />
          <button disabled={!thread}>Rename</button>
        </form>
      </header>

      <section className={styles.messages}>
        {loading && <div className={styles.empty}>Loading workspace...</div>}

        {!loading && !thread && (
          <div className={styles.empty}>Create a conversation to begin.</div>
        )}

        {!loading && thread && messages.length === 0 && (
          <div className={styles.empty}>Ask your first question.</div>
        )}

        {messages.map((message) => (
          <article
            key={message.id}
            className={`${styles.message} ${message.role === 'user' ? styles.user : styles.assistant}`}
          >
            <div className={styles.messageMeta}>
              <strong>{message.role === 'user' ? 'You' : 'Assistant'}</strong>
              <span>{formatTime(message.created_at || message.timestamp)}</span>
            </div>
            <div className={styles.messageBody}>{message.content}</div>
          </article>
        ))}
        <div ref={bottomRef} />
      </section>

      <footer className={styles.composer}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.ctrlKey && e.key === 'Enter') send()
          }}
          placeholder="Message the assistant..."
          disabled={!thread || sending}
        />
        <div className={styles.composerFooter}>
          <span>{sending ? 'Sending...' : status}</span>
          <button onClick={send} disabled={!thread || !prompt.trim() || sending}>
            Send
          </button>
        </div>
      </footer>
    </main>
  )
}
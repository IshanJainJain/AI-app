// frontend/src/components/Sidebar.jsx
import { useState } from 'react'
import styles from './Sidebar.module.css'

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

export default function Sidebar({
  user,
  threads,
  activeThreadId,
  globalContext,
  imageContexts,
  onGlobalContextChange,
  onSaveGlobalContext,
  onClearGlobalContext,
  onCreateThread,
  onSelectThread,
  onDeleteThread,
  onAddImageContext,
  onDeleteImageContext,
  onLogout,
}) {
  const [globalOpen, setGlobalOpen] = useState(true)
  const [imageOpen, setImageOpen] = useState(false)
  const [imageFile, setImageFile] = useState(null)
  const [imagePrompt, setImagePrompt] = useState('')

  const addImage = async () => {
    if (!imageFile) return
    const imageBase64 = await fileToBase64(imageFile)
    await onAddImageContext({
      filename: imageFile.name,
      imageBase64,
      prompt: imagePrompt,
    })
    setImageFile(null)
    setImagePrompt('')
  }

  return (
    <aside className={styles.sidebar}>
      <div className={styles.top}>
        <div>
          <h1>Local AI</h1>
          <p>{user?.username || user?.email || 'Assistant workspace'}</p>
        </div>

        <button className={styles.primaryButton} onClick={onCreateThread}>
          New conversation
        </button>
      </div>

      <div className={styles.threadList}>
        {threads.map((thread) => (
          <button
            key={thread.id}
            className={`${styles.threadItem} ${thread.id === activeThreadId ? styles.active : ''}`}
            onClick={() => onSelectThread(thread.id)}
          >
            <span>
              <strong>{thread.title || 'Untitled conversation'}</strong>
              <small>{thread.message_count ?? thread.messages_count ?? 0} messages</small>
            </span>
            <span
              className={styles.delete}
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation()
                onDeleteThread(thread.id)
              }}
            >
              Delete
            </span>
          </button>
        ))}
      </div>

      <section className={styles.panel}>
        <button className={styles.panelHeader} onClick={() => setGlobalOpen((v) => !v)}>
          Global context
        </button>
        {globalOpen && (
          <div className={styles.panelBody}>
            <textarea
              value={globalContext}
              onChange={(e) => onGlobalContextChange(e.target.value)}
              placeholder="Preferences, background, or standing instructions..."
            />
            <div className={styles.actions}>
              <button onClick={onSaveGlobalContext}>Save</button>
              <button onClick={onClearGlobalContext}>Clear</button>
            </div>
          </div>
        )}
      </section>

      <section className={styles.panel}>
        <button className={styles.panelHeader} onClick={() => setImageOpen((v) => !v)}>
          Image context
        </button>
        {imageOpen && (
          <div className={styles.panelBody}>
            <input type="file" accept="image/*" onChange={(e) => setImageFile(e.target.files?.[0] || null)} />
            <textarea
              value={imagePrompt}
              onChange={(e) => setImagePrompt(e.target.value)}
              placeholder="Optional extraction prompt..."
            />
            <button onClick={addImage} disabled={!imageFile}>Add image</button>

            <div className={styles.contextList}>
              {imageContexts.map((ctx) => (
                <div className={styles.contextItem} key={ctx.id}>
                  <span>{ctx.title || ctx.prompt || 'Image context'}</span>
                  <button onClick={() => onDeleteImageContext(ctx.id)}>Delete</button>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <button className={styles.logout} onClick={onLogout}>Logout</button>
    </aside>
  )
}
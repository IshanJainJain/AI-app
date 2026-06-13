import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus, Trash2, Send, Bot, User, ChevronDown, ChevronRight,
  Wrench, Brain, Upload, X, Loader2,
} from "lucide-react";
import clsx from "clsx";
import { threadsApi, contextApi } from "../services/api";
import { useChat } from "../hooks/useChat";
import type { Thread, Message, WsEvent, AgentThought } from "../types";

function formatTime(iso: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric", minute: "2-digit",
  }).format(new Date(iso));
}

function ThoughtChain({ thoughts }: { thoughts: AgentThought[] }) {
  const [open, setOpen] = useState(false);
  if (!thoughts.length) return null;
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-400"
      >
        <Brain size={12} />
        {thoughts.length} reasoning step{thoughts.length !== 1 ? "s" : ""}
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <div className="mt-2 space-y-2 pl-3 border-l border-gray-700">
          {thoughts.map((t) => (
            <div key={t.step} className="text-xs text-gray-500">
              <span className="text-gray-600 font-mono">Step {t.step}</span>
              {t.action && (
                <span className="ml-2 text-indigo-500">
                  <Wrench size={10} className="inline mr-1" />
                  {t.action}
                </span>
              )}
              {t.thought && <p className="mt-0.5 text-gray-600">{t.thought}</p>}
              {t.observation && (
                <p className="mt-0.5 text-gray-700 font-mono truncate">{t.observation}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <article className={clsx("flex gap-3 max-w-3xl", isUser && "ml-auto flex-row-reverse")}>
      <div
        className={clsx(
          "w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-white",
          isUser ? "bg-indigo-600" : "bg-gray-700"
        )}
      >
        {isUser ? <User size={13} /> : <Bot size={13} />}
      </div>
      <div className={clsx("flex-1", isUser && "items-end flex flex-col")}>
        <div
          className={clsx(
            "rounded-2xl px-4 py-2.5 text-sm",
            isUser
              ? "bg-indigo-600 text-white rounded-tr-sm"
              : "bg-gray-800 text-gray-200 rounded-tl-sm"
          )}
        >
          <div className="prose-chat whitespace-pre-wrap">{message.content}</div>
        </div>
        <div className="flex items-center gap-2 mt-1 px-1">
          <span className="text-xs text-gray-600">{formatTime(message.created_at)}</span>
        </div>
        {!isUser && <ThoughtChain thoughts={message.agent_thoughts ?? []} />}
      </div>
    </article>
  );
}

export default function Chat() {
  const navigate = useNavigate();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThread, setActiveThread] = useState<Thread | null>(null);
  const [globalContext, setGlobalContext] = useState("");
  const [gcOpen, setGcOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const {
    messages,
    streaming,
    sending,
    wsRef: chatWsRef,
    setInitialMessages,
    handleWsEvent,
    sendMessage,
  } = useChat(activeThread?.id ?? null);

  // Keep wsRef in sync with chatWsRef
  wsRef.current = chatWsRef.current;

  // Connect WebSocket when active thread changes
  useEffect(() => {
    if (!activeThread) return;
    const token = localStorage.getItem("token") ?? "";
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(
      `${protocol}://${window.location.host}/ws/chat/${activeThread.id}?token=${token}`
    );
    chatWsRef.current = ws;
    ws.onmessage = (ev) => {
      try {
        handleWsEvent(JSON.parse(ev.data) as WsEvent);
      } catch { /* ignore */ }
    };
    return () => { ws.close(); chatWsRef.current = null; };
  }, [activeThread?.id]);

  // Load threads on mount
  useEffect(() => {
    threadsApi.list().then((r) => {
      const list = r.data.threads;
      setThreads(list);
      if (list.length > 0) loadThread(list[0].id);
    });
    contextApi.getGlobal().then((r) => setGlobalContext(r.data.context));
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  const loadThread = async (id: string) => {
    const r = await threadsApi.get(id);
    setActiveThread(r.data.thread);
    setThreads(r.data.threads);
    setInitialMessages(r.data.messages);
    setGlobalContext(r.data.globalContext);
  };

  const createThread = async () => {
    const r = await threadsApi.create();
    setThreads(r.data.threads);
    setActiveThread(r.data.thread);
    setInitialMessages([]);
  };

  const deleteThread = async (id: string) => {
    const r = await threadsApi.delete(id);
    setThreads(r.data.threads);
    if (r.data.thread) {
      setActiveThread(r.data.thread);
      setInitialMessages(r.data.messages);
    } else {
      setActiveThread(null);
      setInitialMessages([]);
    }
  };

  const handleSend = () => {
    if (!prompt.trim() || sending || !activeThread) return;
    sendMessage(prompt);
    setPrompt("");
  };

  const handleImageUpload = async () => {
    if (!imageFile || !activeThread) return;
    const reader = new FileReader();
    reader.onload = async () => {
      await contextApi.addImage(activeThread.id, imageFile.name, String(reader.result));
      setImageFile(null);
    };
    reader.readAsDataURL(imageFile);
  };

  const saveGlobalContext = async () => {
    await contextApi.setGlobal(globalContext);
    setGcOpen(false);
  };

  return (
    <div className="flex h-full bg-gray-950">
      {/* Thread list sidebar */}
      <div className="w-60 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-800">
          <button
            onClick={createThread}
            className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium py-2 rounded-lg transition-colors"
          >
            <Plus size={14} />
            New conversation
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-1">
          {threads.map((t) => (
            <div
              key={t.id}
              onClick={() => loadThread(t.id)}
              className={clsx(
                "flex items-start justify-between px-3 py-2.5 mx-1 rounded-lg cursor-pointer group transition-colors",
                activeThread?.id === t.id
                  ? "bg-indigo-600/20 border border-indigo-800"
                  : "hover:bg-gray-800"
              )}
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs text-white truncate">{t.title}</p>
                <p className="text-xs text-gray-500">{t.message_count} msgs</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); deleteThread(t.id); }}
                className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 ml-1 flex-shrink-0"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>

        {/* Global context */}
        <div className="border-t border-gray-800">
          <button
            onClick={() => setGcOpen((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-gray-400 hover:text-white transition-colors"
          >
            <span>Global context</span>
            {gcOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </button>
          {gcOpen && (
            <div className="px-3 pb-3">
              <textarea
                value={globalContext}
                onChange={(e) => setGlobalContext(e.target.value)}
                rows={4}
                placeholder="Standing instructions..."
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-indigo-600 resize-none"
              />
              <button
                onClick={saveGlobalContext}
                className="mt-1.5 w-full bg-gray-700 hover:bg-gray-600 text-white text-xs py-1.5 rounded-lg transition-colors"
              >
                Save
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="px-6 py-3.5 border-b border-gray-800 bg-gray-900/50">
          <p className="text-sm font-medium text-white">
            {activeThread?.title ?? "Select or create a conversation"}
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {!activeThread && (
            <div className="flex items-center justify-center h-full text-gray-600 text-sm">
              Create a new conversation to begin
            </div>
          )}

          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}

          {/* Streaming indicator */}
          {streaming && (
            <div className="flex gap-3 max-w-3xl">
              <div className="w-7 h-7 rounded-full bg-gray-700 flex-shrink-0 flex items-center justify-center">
                <Bot size={13} className="text-white" />
              </div>
              <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-2.5">
                {streaming.toolCalls.length > 0 && (
                  <div className="flex items-center gap-1.5 text-xs text-indigo-400 mb-1">
                    <Wrench size={12} />
                    {streaming.toolCalls[streaming.toolCalls.length - 1].tool}
                  </div>
                )}
                {streaming.thinking.length > 0 && (
                  <p className="text-xs text-gray-500 italic truncate max-w-xs">
                    {streaming.thinking[streaming.thinking.length - 1]}
                  </p>
                )}
                <div className="flex gap-1 mt-1">
                  <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Composer */}
        <div className="px-6 py-4 border-t border-gray-800 bg-gray-900/30">
          {imageFile && (
            <div className="flex items-center gap-2 mb-2 text-xs text-gray-400">
              <span className="truncate max-w-xs">{imageFile.name}</span>
              <button onClick={() => setImageFile(null)} className="text-gray-600 hover:text-gray-300">
                <X size={12} />
              </button>
              <button
                onClick={handleImageUpload}
                className="ml-auto text-indigo-400 hover:text-indigo-300"
              >
                Upload image
              </button>
            </div>
          )}

          <div className="flex items-end gap-2">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={!activeThread}
              className="text-gray-600 hover:text-gray-400 disabled:opacity-30 flex-shrink-0 pb-2"
            >
              <Upload size={16} />
            </button>

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={activeThread ? "Message the assistant... (Enter to send)" : "Select a conversation first"}
              disabled={!activeThread || sending}
              rows={1}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-600 resize-none disabled:opacity-50"
              style={{ maxHeight: "120px", overflowY: "auto" }}
            />

            <button
              onClick={handleSend}
              disabled={!activeThread || !prompt.trim() || sending}
              className="flex-shrink-0 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white p-2.5 rounded-xl transition-colors"
            >
              {sending
                ? <Loader2 size={16} className="animate-spin" />
                : <Send size={16} />
              }
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

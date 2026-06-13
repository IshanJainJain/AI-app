// ── Auth ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  username: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// ── Threads & messages ────────────────────────────────────────────────────────

export interface Thread {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface AgentThought {
  step: number;
  thought: string;
  action?: string;
  action_input?: Record<string, unknown>;
  observation?: string;
}

export interface ToolCallLog {
  step: number;
  tool: string;
  params: Record<string, unknown>;
  result: unknown;
  success: boolean;
  timestamp: string;
}

export interface Message {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  agent_thoughts?: AgentThought[];
  tool_calls?: ToolCallLog[];
  created_at: string;
}

export interface ImageContext {
  id: string;
  thread_id: string;
  filename: string;
  description: string;
  model: string;
  created_at: string;
}

export interface ThreadPayload {
  thread: Thread;
  threads: Thread[];
  messages: Message[];
  globalContext: string;
  imageContexts: ImageContext[];
}

// ── Knowledge base ────────────────────────────────────────────────────────────

export interface KBFolder {
  name: string;
  path: string;
}

export interface KBFile {
  name: string;
  path: string;
  size: number;
}

export interface KBPayload {
  path: string;
  parent: string;
  folders: KBFolder[];
  files: KBFile[];
  ingestion?: { chunks: number; embedding_model: string };
}

export interface ChunkRecord {
  id: number;
  chunk: number;
  text: string;
  metadata: {
    source: string;
    sha256: string;
    embedding_model: string;
    chunking_model: string;
  };
}

export interface ChunksPayload {
  source: string;
  chunks: ChunkRecord[];
}

// ── WebSocket events ──────────────────────────────────────────────────────────

export type WsEventType =
  | "connected"
  | "agent_thinking"
  | "tool_call"
  | "tool_result"
  | "agent_response"
  | "message_saved"
  | "done"
  | "error";

export interface WsEvent {
  type: WsEventType;
  content?: string;
  step?: number;
  tool?: string;
  params?: Record<string, unknown>;
  data?: unknown;
  thoughts?: AgentThought[];
  tool_calls?: ToolCallLog[];
  message_id?: string;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_threads: number;
  total_messages: number;
  total_kb_documents: number;
  active_users: number;
}

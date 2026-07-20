import axios from "axios";
import type {
  TokenResponse, User, ThreadPayload, Thread,
  KBPayload, ChunksPayload, ImageContext, KBHealthPayload,
} from "../types";

// When embedded as MFE, set VITE_CHATBOT_API_BASE to the absolute chatbot backend URL.
// Leave empty (default) for standalone deployment where nginx proxies /api/.
const API_BASE = (import.meta.env.VITE_CHATBOT_API_BASE ?? "") + "/api/v1";

const api = axios.create({ baseURL: API_BASE });

// Attach JWT from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// ── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  register: (email: string, username: string, password: string) =>
    api.post<TokenResponse>("/auth/register", { email, username, password }),

  login: (login: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { login, password }),

  me: () => api.get<User>("/users/me"),
};

// ── Threads ───────────────────────────────────────────────────────────────────

export const threadsApi = {
  list: () => api.get<{ threads: Thread[] }>("/threads"),

  create: (title = "New conversation") =>
    api.post<ThreadPayload>("/threads", { title }),

  get: (id: string) => api.get<ThreadPayload>(`/threads/${id}`),

  rename: (id: string, title: string) =>
    api.patch<ThreadPayload>(`/threads/${id}`, { title }),

  delete: (id: string) => api.delete<ThreadPayload>(`/threads/${id}`),

  prompt: (id: string, prompt: string) =>
    api.post<ThreadPayload>(`/threads/${id}/prompt`, { prompt }),
};

// ── Context ───────────────────────────────────────────────────────────────────

export const contextApi = {
  getGlobal: () => api.get<{ context: string }>("/global-context"),
  setGlobal: (context: string) => api.put<{ context: string }>("/global-context", { context }),
  deleteGlobal: () => api.delete<{ context: string }>("/global-context"),

  listImages: (threadId: string) =>
    api.get<{ imageContexts: ImageContext[] }>(`/threads/${threadId}/image-contexts`),

  addImage: (threadId: string, filename: string, image: string, prompt?: string) =>
    api.post<{ imageContexts: ImageContext[] }>(`/threads/${threadId}/image-contexts`, {
      filename, image, prompt,
    }),

  deleteImage: (threadId: string, ctxId: string) =>
    api.delete<{ imageContexts: ImageContext[] }>(`/threads/${threadId}/image-contexts/${ctxId}`),
};

// ── Knowledge base ────────────────────────────────────────────────────────────

export const kbApi = {
  browse: (path = "") => api.get<KBPayload>(`/knowledge-base?path=${encodeURIComponent(path)}`),

  createFolder: (parent: string, name: string) =>
    api.post<KBPayload>("/knowledge-base/folders", { parent, name }),

  upload: (parent: string, file: File) => {
    const form = new FormData();
    form.append("parent", parent);
    form.append("file", file);
    return api.post<KBPayload>("/knowledge-base/files", form);
  },

  getChunks: (path: string) =>
    api.get<ChunksPayload>(`/knowledge-base/files/chunks?path=${encodeURIComponent(path)}`),

  health: () => api.get<KBHealthPayload>("/admin/kb/health"),
};

export default api;

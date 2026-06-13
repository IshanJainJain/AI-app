/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute base URL for the chatbot backend API (e.g. http://localhost:8001).
   *  Leave unset when running standalone — nginx proxies /api/ to backend. */
  readonly VITE_CHATBOT_API_BASE?: string;
  /** host:port of the chatbot backend WebSocket (e.g. localhost:8001).
   *  Leave unset when running standalone — defaults to window.location.host. */
  readonly VITE_CHATBOT_WS_HOST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

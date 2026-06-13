import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import federation from "@originjs/vite-plugin-federation";

export default defineConfig({
  plugins: [
    react(),
    federation({
      name: "chatbot",
      filename: "remoteEntry.js",
      exposes: {
        // Host app imports: import ChatApp from 'chatbot/App'
        "./App": "./src/App",
        // Lightweight embeddable widget
        "./ChatPage": "./src/pages/Chat",
      },
      shared: {
        react: { singleton: true, requiredVersion: "^18.3.1" },
        "react-dom": { singleton: true, requiredVersion: "^18.3.1" },
        "react-router-dom": { singleton: true, requiredVersion: "^6.26.2" },
      },
    }),
  ],
  server: {
    port: 5174,  // 5173 reserved for invoice-platform dev server
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: {
    // Required for Module Federation
    modulePreload: false,
    target: "esnext",
    minify: false,
    cssCodeSplit: false,
  },
});

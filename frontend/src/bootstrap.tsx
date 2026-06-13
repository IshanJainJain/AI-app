/**
 * Async entry point required by Vite Module Federation.
 *
 * main.tsx does: import('./bootstrap')
 *
 * This indirection lets Module Federation load shared singletons
 * (react, react-dom) before the app tree mounts, which prevents
 * the "Eager Consumption" error when this remote is consumed by a host.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);

from html import escape
import json

from knowledge_base_templates import (
    KNOWLEDGE_BASE_BINDINGS,
    KNOWLEDGE_BASE_CSS,
    KNOWLEDGE_BASE_EVENTS,
    KNOWLEDGE_BASE_MOBILE_CSS,
    KNOWLEDGE_BASE_SCRIPT,
    render_knowledge_menu_button,
    render_knowledge_panel,
)


def render_page(threads, messages, active_thread_id: int, global_context: str, model: str) -> str:
    initial_state = json.dumps({
        "threads": threads,
        "messages": messages,
        "activeThreadId": active_thread_id,
        "globalContext": global_context,
    })

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Local AI App</title>
    <style>
        :root {{
            color-scheme: light;
            --bg: #f5f6f2;
            --panel: #ffffff;
            --panel-alt: #eef4f1;
            --text: #17211d;
            --muted: #657169;
            --line: #d9dfda;
            --accent: #0f766e;
            --accent-dark: #115e59;
            --danger: #b42318;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            height: 100vh;
            overflow: hidden;
            background: var(--bg);
            color: var(--text);
        }}

        .app {{
            display: grid;
            grid-template-columns: 78px minmax(0, 1fr);
            height: 100vh;
            min-height: 0;
        }}

        .menu-rail {{
            display: flex;
            flex-direction: column;
            gap: 10px;
            align-items: stretch;
            border-right: 1px solid #cfd8d2;
            background: #111c18;
            padding: 12px 8px;
            min-width: 0;
            min-height: 0;
        }}

        .menu-mark {{
            display: grid;
            place-items: center;
            width: 44px;
            height: 44px;
            margin: 0 auto 8px;
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 8px;
            color: white;
            font-size: 18px;
            font-weight: 900;
        }}

        .menu-button {{
            display: grid;
            place-items: center;
            gap: 4px;
            width: 100%;
            min-height: 58px;
            border: 1px solid transparent;
            border-radius: 8px;
            background: transparent;
            color: #dbe8e2;
            padding: 6px 4px;
            text-align: center;
            font-size: 12px;
            line-height: 1.1;
        }}

        .menu-button:hover {{
            border-color: rgba(255, 255, 255, 0.18);
            background: rgba(255, 255, 255, 0.08);
        }}

        .menu-button.active {{
            border-color: rgba(255, 255, 255, 0.28);
            background: #0f766e;
            color: white;
        }}

        .menu-icon {{
            font-size: 20px;
            line-height: 1;
        }}

        .menu-content {{
            min-width: 0;
            min-height: 0;
        }}

        .menu-panel {{
            display: none;
            min-width: 0;
            min-height: 0;
            height: 100vh;
        }}

        .menu-panel.active {{
            display: block;
        }}

        .chat-layout {{
            display: grid;
            grid-template-columns: 300px minmax(0, 1fr);
            height: 100vh;
            min-height: 0;
        }}

        .sidebar {{
            display: flex;
            flex-direction: column;
            gap: 14px;
            border-right: 1px solid var(--line);
            background: #fbfcfa;
            padding: 18px;
            min-width: 0;
            min-height: 0;
        }}

        .brand {{
            display: flex;
            align-items: start;
            justify-content: space-between;
            gap: 10px;
        }}

        h1 {{
            margin: 0;
            font-size: 22px;
            line-height: 1.15;
        }}

        .model {{
            color: var(--muted);
            font-size: 13px;
            margin-top: 4px;
        }}

        button {{
            border: 0;
            border-radius: 8px;
            background: var(--accent);
            color: white;
            min-height: 40px;
            padding: 0 14px;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
        }}

        button:hover {{
            background: var(--accent-dark);
        }}

        button:disabled {{
            cursor: wait;
            opacity: 0.72;
        }}

        .icon-button {{
            width: 40px;
            padding: 0;
            flex: 0 0 auto;
        }}

        .thread-list {{
            display: grid;
            gap: 8px;
            flex: 1 1 auto;
            min-height: 0;
            overflow-y: auto;
            padding-right: 2px;
        }}

        .global-context {{
            display: grid;
            gap: 8px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            padding: 12px;
        }}

        .global-context summary {{
            cursor: pointer;
            color: var(--text);
            font-size: 14px;
            font-weight: 800;
            list-style-position: inside;
        }}

        .global-context-content {{
            display: grid;
            gap: 8px;
            margin-top: 10px;
        }}

        .global-context textarea {{
            min-height: 110px;
            max-height: 180px;
            padding: 10px;
            font-size: 14px;
        }}

        .global-context .actions {{
            margin-top: 0;
        }}

        .global-context button {{
            min-height: 36px;
        }}

        .thread-button {{
            display: grid;
            gap: 5px;
            width: 100%;
            min-height: 62px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            color: var(--text);
            padding: 10px;
            text-align: left;
        }}

        .thread-button:hover {{
            background: var(--panel-alt);
        }}

        .thread-button.active {{
            border-color: var(--accent);
            background: #e7f5f2;
        }}

        .thread-title {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-weight: 800;
        }}

        .thread-meta {{
            color: var(--muted);
            font-size: 12px;
        }}

        .workspace {{
            display: grid;
            grid-template-rows: auto minmax(0, 1fr) auto;
            min-width: 0;
            min-height: 0;
            height: 100vh;
        }}

        .topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            border-bottom: 1px solid var(--line);
            background: var(--panel);
            padding: 16px 22px;
            min-width: 0;
        }}

        .active-title {{
            margin: 0;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 20px;
        }}

        .rename-form {{
            display: flex;
            gap: 8px;
            align-items: center;
            min-width: 0;
        }}

        .rename-input {{
            width: min(420px, 44vw);
            min-height: 40px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0 12px;
            font: inherit;
        }}

        .messages {{
            display: flex;
            flex-direction: column;
            gap: 14px;
            overflow-y: auto;
            padding: 22px;
        }}

        .message {{
            flex: 0 0 auto;
            width: min(760px, 100%);
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            overflow: hidden;
        }}

        .message.user {{
            align-self: flex-end;
            background: #f0f7ff;
        }}

        .message.assistant {{
            align-self: flex-start;
        }}

        .message-header {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 10px 12px;
            background: rgba(15, 118, 110, 0.08);
            color: var(--muted);
            font-size: 13px;
        }}

        pre {{
            margin: 0;
            padding: 13px;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            font: inherit;
            line-height: 1.5;
        }}

        .empty-state {{
            margin: auto;
            width: min(460px, 100%);
            border: 1px dashed var(--line);
            border-radius: 8px;
            padding: 24px;
            text-align: center;
            color: var(--muted);
            background: rgba(255, 255, 255, 0.65);
        }}

        .empty-state h2 {{
            margin: 0 0 6px;
            color: var(--text);
            font-size: 20px;
        }}

        .empty-state p {{
            margin: 0;
        }}

        .composer {{
            border-top: 1px solid var(--line);
            background: var(--panel);
            padding: 16px 22px;
        }}

        label {{
            display: block;
            color: var(--muted);
            font-size: 14px;
            margin-bottom: 8px;
        }}

        textarea {{
            width: 100%;
            min-height: 120px;
            max-height: 300px;
            resize: vertical;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px;
            color: var(--text);
            font: inherit;
            line-height: 1.45;
            outline: none;
        }}

        textarea:focus,
        .rename-input:focus {{
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.14);
            outline: none;
        }}

        .actions {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: 12px;
        }}

        .status {{
            color: var(--muted);
            font-size: 14px;
        }}

        .status.error {{
            color: var(--danger);
        }}

        {KNOWLEDGE_BASE_CSS}

        @media (max-width: 800px) {{
            body {{
                overflow: hidden;
            }}

            .app {{
                grid-template-columns: 60px minmax(0, 1fr);
                height: 100vh;
                min-height: 0;
            }}

            .menu-rail {{
                padding: 8px 6px;
            }}

            .menu-mark {{
                width: 38px;
                height: 38px;
                font-size: 16px;
            }}

            .menu-button {{
                min-height: 52px;
                font-size: 11px;
                padding: 5px 2px;
            }}

            .menu-icon {{
                font-size: 18px;
            }}

            .chat-layout {{
                grid-template-columns: 1fr;
                grid-template-rows: minmax(200px, 30vh) minmax(0, 1fr);
                height: 100vh;
                min-height: 0;
            }}

            .sidebar {{
                border-right: 0;
                border-bottom: 1px solid var(--line);
                min-height: 0;
                overflow: hidden;
                gap: 8px;
                padding: 10px;
            }}

            h1 {{
                font-size: 18px;
            }}

            .model {{
                font-size: 12px;
            }}

            .icon-button {{
                min-height: 34px;
                width: 34px;
            }}

            .global-context textarea {{
                min-height: 68px;
                max-height: 96px;
            }}

            .thread-list {{
                max-height: none;
                min-height: 90px;
            }}

            .thread-button {{
                min-height: 50px;
                padding: 8px;
            }}

            .workspace {{
                height: auto;
                min-height: 0;
                max-height: none;
            }}

            .topbar {{
                align-items: center;
                flex-direction: row;
                padding: 10px;
            }}

            .active-title {{
                font-size: 18px;
            }}

            .rename-form {{
                flex: 0 1 58%;
            }}

            .rename-input {{
                width: 100%;
                min-height: 34px;
            }}

            .rename-form button {{
                min-height: 34px;
            }}

            .messages {{
                padding: 10px;
            }}

            .composer {{
                padding: 10px;
            }}

            textarea {{
                min-height: 72px;
                max-height: 140px;
            }}

            .composer .actions {{
                margin-top: 8px;
            }}

            {KNOWLEDGE_BASE_MOBILE_CSS}

        }}
    </style>
</head>
<body>
    <main class="app">
        <nav class="menu-rail" aria-label="Main menu">
            <div class="menu-mark" aria-hidden="true">AI</div>
            <button class="menu-button active" type="button" data-menu="chat" aria-controls="chat-panel" aria-current="page">
                <span class="menu-icon" aria-hidden="true">#</span>
                <span>Chat</span>
            </button>
            {render_knowledge_menu_button()}
        </nav>

        <div class="menu-content">
            <section class="menu-panel active" id="chat-panel" data-panel="chat">
                <div class="chat-layout">
                    <aside class="sidebar">
                        <div class="brand">
                            <div>
                                <h1>Local AI App</h1>
                                <div class="model">Model: {escape(model)}</div>
                            </div>
                            <button class="icon-button" id="new-thread" type="button" title="New conversation">+</button>
                        </div>
                        <details class="global-context">
                            <summary>Global context</summary>
                            <div class="global-context-content">
                                <label for="global-context">Shared across all conversations</label>
                                <textarea id="global-context" placeholder="Shared instructions, facts, preferences, or background for every conversation..."></textarea>
                                <div class="actions">
                                    <button id="save-global-context" type="button">Save context</button>
                                    <span class="status" id="global-context-status"></span>
                                </div>
                            </div>
                        </details>
                        <nav class="thread-list" id="thread-list" aria-label="Conversations"></nav>
                    </aside>

                    <section class="workspace">
                        <header class="topbar">
                            <h2 class="active-title" id="active-title">Conversation</h2>
                            <form class="rename-form" id="rename-form">
                                <input class="rename-input" id="rename-input" type="text" aria-label="Conversation title">
                                <button type="submit">Rename</button>
                            </form>
                        </header>

                        <section class="messages" id="messages"></section>

                        <section class="composer">
                            <label for="prompt">Prompt</label>
                            <textarea id="prompt" placeholder="Continue this conversation..."></textarea>
                            <div class="actions">
                                <button id="send" type="button">Send prompt</button>
                                <span class="status" id="status"></span>
                            </div>
                        </section>
                    </section>
                </div>
            </section>

            {render_knowledge_panel()}
        </div>
    </main>

    <script>
        const state = {initial_state};
        const storageKey = "local-ai-active-thread-id";

        const threadList = document.querySelector("#thread-list");
        const messagesPanel = document.querySelector("#messages");
        const activeTitle = document.querySelector("#active-title");
        const renameForm = document.querySelector("#rename-form");
        const renameInput = document.querySelector("#rename-input");
        const promptBox = document.querySelector("#prompt");
        const sendButton = document.querySelector("#send");
        const statusText = document.querySelector("#status");
        const newThreadButton = document.querySelector("#new-thread");
        const globalContextBox = document.querySelector("#global-context");
        const saveGlobalContextButton = document.querySelector("#save-global-context");
        const globalContextStatus = document.querySelector("#global-context-status");
        const menuButtons = document.querySelectorAll(".menu-button");
        const menuPanels = document.querySelectorAll(".menu-panel");
        {KNOWLEDGE_BASE_BINDINGS}

        function showMenu(menu) {{
            menuButtons.forEach((button) => {{
                const isActive = button.dataset.menu === menu;
                button.classList.toggle("active", isActive);
                button.setAttribute("aria-current", isActive ? "page" : "false");
            }});
            menuPanels.forEach((panel) => {{
                panel.classList.toggle("active", panel.dataset.panel === menu);
            }});
            if (menu === "knowledge" && !state.knowledgeBase.loaded) {{
                loadKnowledgeBase("");
            }}
        }}

        function escapeHtml(value) {{
            return String(value || "").replace(/[&<>"']/g, (char) => ({{
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            }}[char]));
        }}

        function activeThread() {{
            return state.threads.find((thread) => thread.id === state.activeThreadId) || state.threads[0];
        }}

        {KNOWLEDGE_BASE_SCRIPT}

        function setStatus(message, isError = false) {{
            statusText.textContent = message;
            statusText.classList.toggle("error", isError);
        }}

        function setGlobalContextStatus(message, isError = false) {{
            globalContextStatus.textContent = message;
            globalContextStatus.classList.toggle("error", isError);
        }}

        function renderThreads() {{
            threadList.innerHTML = state.threads.map((thread) => `
                <button
                    class="thread-button ${{thread.id === state.activeThreadId ? "active" : ""}}"
                    type="button"
                    data-thread-id="${{thread.id}}"
                >
                    <span class="thread-title">${{escapeHtml(thread.title)}}</span>
                    <span class="thread-meta">${{thread.message_count || 0}} messages</span>
                </button>
            `).join("");

            threadList.querySelectorAll(".thread-button").forEach((button) => {{
                button.addEventListener("click", () => loadThread(Number(button.dataset.threadId)));
            }});
        }}

        function renderMessages() {{
            const thread = activeThread();
            activeTitle.textContent = thread ? thread.title : "Conversation";
            renameInput.value = thread ? thread.title : "";

            if (!state.messages.length) {{
                messagesPanel.innerHTML = `
                    <section class="empty-state">
                        <h2>New conversation</h2>
                        <p>Send the first prompt here. This thread will keep its own context and be restored when you reopen the app.</p>
                    </section>
                `;
                return;
            }}

            messagesPanel.innerHTML = state.messages.map((message) => `
                <article class="message ${{escapeHtml(message.role)}}">
                    <div class="message-header">
                        <strong>${{message.role === "user" ? "You" : "Assistant"}}</strong>
                        <span>${{escapeHtml(message.created_at)}}</span>
                    </div>
                    <pre>${{escapeHtml(message.content)}}</pre>
                </article>
            `).join("");
            messagesPanel.scrollTop = messagesPanel.scrollHeight;
        }}

        function render() {{
            globalContextBox.value = state.globalContext || "";
            renderThreads();
            renderMessages();
        }}

        function updateFromPayload(data) {{
            state.threads = data.threads;
            state.messages = data.messages;
            state.activeThreadId = data.thread.id;
            state.globalContext = data.globalContext ?? state.globalContext ?? "";
            localStorage.setItem(storageKey, String(state.activeThreadId));
            render();
        }}

        async function saveGlobalContext() {{
            saveGlobalContextButton.disabled = true;
            setGlobalContextStatus("Saving...");
            try {{
                const response = await fetch("/api/global-context", {{
                    method: "PUT",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ context: globalContextBox.value }})
                }});
                if (!response.ok) {{
                    throw new Error("Could not save global context.");
                }}
                const data = await response.json();
                state.globalContext = data.context;
                globalContextBox.value = state.globalContext;
                setGlobalContextStatus("Saved.");
            }} catch (error) {{
                setGlobalContextStatus(error.message, true);
            }} finally {{
                saveGlobalContextButton.disabled = false;
            }}
        }}

        async function loadThread(threadId) {{
            setStatus("");
            const response = await fetch(`/api/threads/${{threadId}}`);
            if (!response.ok) {{
                setStatus("Could not load that conversation.", true);
                return;
            }}
            updateFromPayload(await response.json());
        }}

        async function loadStoredThread() {{
            const storedThreadId = Number(localStorage.getItem(storageKey));
            if (!storedThreadId || storedThreadId === state.activeThreadId) {{
                render();
                return;
            }}
            if (state.threads.some((thread) => thread.id === storedThreadId)) {{
                await loadThread(storedThreadId);
                return;
            }}
            render();
        }}

        async function createThread() {{
            newThreadButton.disabled = true;
            setStatus("");
            try {{
                const response = await fetch("/api/threads", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ title: "New conversation" }})
                }});
                if (!response.ok) {{
                    throw new Error("Could not create conversation.");
                }}
                updateFromPayload(await response.json());
                promptBox.focus();
            }} catch (error) {{
                setStatus(error.message, true);
            }} finally {{
                newThreadButton.disabled = false;
            }}
        }}

        async function renameThread(event) {{
            event.preventDefault();
            const title = renameInput.value.trim();
            if (!title) {{
                setStatus("Title cannot be empty.", true);
                return;
            }}

            try {{
                const response = await fetch(`/api/threads/${{state.activeThreadId}}`, {{
                    method: "PATCH",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ title }})
                }});
                if (!response.ok) {{
                    throw new Error("Could not rename conversation.");
                }}
                updateFromPayload(await response.json());
                setStatus("Renamed.");
            }} catch (error) {{
                setStatus(error.message, true);
            }}
        }}

        async function sendPrompt() {{
            const prompt = promptBox.value.trim();
            if (!prompt) {{
                setStatus("Write a prompt first.", true);
                promptBox.focus();
                return;
            }}

            sendButton.disabled = true;
            setStatus("Sending...");
            const statusTimers = [
                window.setTimeout(() => setStatus("Retrieving knowledge base context..."), 3000),
                window.setTimeout(() => setStatus("Generating answer with the local model..."), 15000),
                window.setTimeout(() => setStatus("Still working. Local models can take a few minutes on a VM."), 60000)
            ];

            try {{
                const response = await fetch(`/api/threads/${{state.activeThreadId}}/prompt`, {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ prompt }})
                }});
                if (!response.ok) {{
                    throw new Error(`Request failed with status ${{response.status}}`);
                }}
                updateFromPayload(await response.json());
                promptBox.value = "";
                setStatus("Saved.");
            }} catch (error) {{
                setStatus(error.message, true);
            }} finally {{
                statusTimers.forEach((timer) => window.clearTimeout(timer));
                sendButton.disabled = false;
            }}
        }}

        newThreadButton.addEventListener("click", createThread);
        saveGlobalContextButton.addEventListener("click", saveGlobalContext);
        renameForm.addEventListener("submit", renameThread);
        sendButton.addEventListener("click", sendPrompt);
        {KNOWLEDGE_BASE_EVENTS}
        menuButtons.forEach((button) => {{
            button.addEventListener("click", () => showMenu(button.dataset.menu));
        }});
        promptBox.addEventListener("keydown", (event) => {{
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {{
                sendPrompt();
            }}
        }});

        loadStoredThread();
    </script>
</body>
</html>"""

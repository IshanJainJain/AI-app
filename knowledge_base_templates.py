KNOWLEDGE_BASE_CSS = """
        .knowledge-base {
            display: grid;
            grid-template-rows: auto auto minmax(0, 1fr);
            height: 100vh;
            min-height: 0;
            background: var(--bg);
        }

        .kb-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            border-bottom: 1px solid var(--line);
            background: var(--panel);
            padding: 18px 22px;
            min-width: 0;
        }

        .kb-header h2 {
            margin: 0;
            font-size: 22px;
        }

        .kb-path {
            color: var(--muted);
            font-size: 14px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .kb-tools {
            display: grid;
            grid-template-columns: minmax(220px, 320px) minmax(260px, 420px);
            gap: 14px;
            border-bottom: 1px solid var(--line);
            background: #fbfcfa;
            padding: 16px 22px;
        }

        .kb-form {
            display: grid;
            gap: 8px;
            min-width: 0;
        }

        .kb-form-row {
            display: flex;
            gap: 8px;
            min-width: 0;
        }

        .kb-input {
            width: 100%;
            min-height: 40px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0 12px;
            font: inherit;
        }

        .kb-input:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.14);
            outline: none;
        }

        .kb-file-input {
            width: 100%;
            min-height: 40px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            padding: 8px;
            font: inherit;
        }

        .kb-entry-indexing {
            flex-direction: column;
            align-items: stretch;
        }

        .kb-entry-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            width: 100%;
        }

        .kb-file-progress {
            display: grid;
            gap: 6px;
            width: 100%;
        }

        .kb-file-progress-label {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
        }

        .kb-progress-percent {
            color: var(--accent-dark);
            font-variant-numeric: tabular-nums;
        }

        .kb-progress-track {
            overflow: hidden;
            width: 100%;
            height: 8px;
            border-radius: 999px;
            background: #e8ece9;
        }

        .kb-progress-bar {
            width: 0%;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, var(--accent), #14b8a6);
            transition: width 0.25s ease;
        }

        .kb-content {
            min-height: 0;
            overflow-y: auto;
            padding: 22px;
        }

        .kb-browser {
            display: grid;
            gap: 10px;
            max-width: 920px;
        }

        .kb-entry {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            width: 100%;
            min-height: 54px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            color: var(--text);
            padding: 10px 12px;
            text-align: left;
        }

        .kb-entry:hover {
            background: var(--panel-alt);
        }

        .kb-entry-main {
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 0;
        }

        .kb-entry-icon {
            display: grid;
            place-items: center;
            width: 32px;
            height: 32px;
            border-radius: 8px;
            background: #e7f5f2;
            color: var(--accent-dark);
            flex: 0 0 auto;
            font-weight: 900;
        }

        .kb-entry-name {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-weight: 800;
        }

        .kb-entry-meta {
            color: var(--muted);
            font-size: 13px;
            flex: 0 0 auto;
        }

        .kb-delete {
            width: 34px;
            min-height: 34px;
            padding: 0;
            border-radius: 8px;
            background: #f3f4f6;
            color: var(--danger);
            font-size: 18px;
            line-height: 1;
            flex: 0 0 auto;
        }

        .kb-delete:hover {
            background: #fee4e2;
        }

        .kb-empty {
            width: min(520px, 100%);
            border: 1px dashed var(--line);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.72);
            padding: 24px;
            color: var(--muted);
        }

        .kb-empty h3 {
            margin: 0 0 6px;
            color: var(--text);
            font-size: 20px;
        }

        .kb-empty p {
            margin: 0;
        }

        .kb-chunk-view {
            display: grid;
            gap: 14px;
            max-width: 980px;
        }

        .kb-chunk-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            padding: 12px;
        }

        .kb-chunk-title {
            min-width: 0;
        }

        .kb-chunk-title h3 {
            margin: 0 0 4px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 18px;
        }

        .kb-chunk-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            overflow: hidden;
        }

        .kb-chunk-card header {
            border-bottom: 1px solid var(--line);
            background: rgba(15, 118, 110, 0.08);
            color: var(--muted);
            padding: 10px 12px;
            font-size: 13px;
            font-weight: 800;
        }

        .kb-chunk-card pre {
            padding: 12px;
        }
"""

KNOWLEDGE_BASE_MOBILE_CSS = """
            .knowledge-base {
                grid-template-rows: auto auto minmax(0, 1fr);
            }

            .kb-header {
                align-items: flex-start;
                flex-direction: column;
                padding: 12px;
            }

            .kb-tools {
                grid-template-columns: 1fr;
                padding: 12px;
            }

            .kb-form-row {
                flex-direction: column;
            }

            .kb-content {
                padding: 12px;
            }
"""

KNOWLEDGE_BASE_BINDINGS = """
        const kbPath = document.querySelector("#kb-path");
        const kbUpButton = document.querySelector("#kb-up");
        const kbBrowser = document.querySelector("#kb-browser");
        const kbStatus = document.querySelector("#kb-status");
        const kbFolderForm = document.querySelector("#kb-folder-form");
        const kbFolderName = document.querySelector("#kb-folder-name");
        const kbUploadForm = document.querySelector("#kb-upload-form");
        const kbFile = document.querySelector("#kb-file");

        state.knowledgeBase = {
            path: "",
            parent: "",
            folders: [],
            files: [],
            activeIngestions: [],
            loaded: false
        };
        state.kbIngestionPollTimer = null;
"""

KNOWLEDGE_BASE_SCRIPT = """
        function formatBytes(size) {
            if (size < 1024) {
                return `${size} B`;
            }
            if (size < 1024 * 1024) {
                return `${(size / 1024).toFixed(1)} KB`;
            }
            return `${(size / 1024 / 1024).toFixed(1)} MB`;
        }

        function setKnowledgeStatus(message, isError = false) {
            kbStatus.textContent = message;
            kbStatus.classList.toggle("error", isError);
        }

        function mergeActiveIngestions(data) {
            const active = data.active_ingestions || [];
            const fromFiles = (data.files || [])
                .map((file) => file.ingestion)
                .filter(Boolean);
            const merged = new Map();
            [...active, ...fromFiles].forEach((job) => {
                if (job && job.job_id) {
                    merged.set(job.job_id, job);
                }
            });
            return Array.from(merged.values());
        }

        function applyIngestionsToFiles() {
            const jobBySource = new Map(
                (state.knowledgeBase.activeIngestions || []).map((job) => [job.source, job])
            );
            state.knowledgeBase.files = (state.knowledgeBase.files || []).map((file) => {
                const job = jobBySource.get(file.path);
                if (!job) {
                    const { ingestion, ...rest } = file;
                    return rest;
                }
                return { ...file, ingestion: job };
            });
        }

        function chunkingDisplayPercent(ingestion) {
            return Math.max(0, Math.min(100, Math.round(ingestion.chunking_progress || 0)));
        }

        function renderFileProgress(ingestion) {
            if (!ingestion || ingestion.phase === "complete" || ingestion.phase === "failed") {
                return "";
            }

            const percent = chunkingDisplayPercent(ingestion);
            const phaseLabels = {
                queued: "Preparing",
                parsing: "Preparing",
                chunking: "Chunking",
                embedding: "Indexing"
            };
            const label = phaseLabels[ingestion.phase] || "Processing";

            return `
                <div class="kb-file-progress">
                    <div class="kb-file-progress-label">
                        <span>${label}</span>
                        <span class="kb-progress-percent">${percent}%</span>
                    </div>
                    <div class="kb-progress-track">
                        <div class="kb-progress-bar" style="width: ${percent}%"></div>
                    </div>
                </div>
            `;
        }

        function stopIngestionPolling() {
            if (state.kbIngestionPollTimer) {
                window.clearInterval(state.kbIngestionPollTimer);
                state.kbIngestionPollTimer = null;
            }
        }

        function ensureIngestionPolling() {
            if (state.kbIngestionPollTimer) {
                return;
            }

            const poll = async () => {
                try {
                    const response = await fetch("/api/knowledge-base/ingestion");
                    if (!response.ok) {
                        return;
                    }

                    const payload = await response.json();
                    const jobs = payload.jobs || [];
                    state.knowledgeBase.activeIngestions = jobs;
                    applyIngestionsToFiles();
                    renderKnowledgeBase();

                    if (!jobs.length) {
                        stopIngestionPolling();
                    }
                } catch (error) {
                    console.error(error);
                }
            };

            poll();
            state.kbIngestionPollTimer = window.setInterval(poll, 1200);
        }

        function renderKnowledgeBase() {
            applyIngestionsToFiles();
            const data = state.knowledgeBase;
            kbPath.textContent = data.path ? `/${data.path}` : "/";
            kbUpButton.disabled = !data.path;

            const parentEntry = data.path ? `
                <button class="kb-entry" type="button" data-kb-path="${escapeHtml(data.parent)}" data-kb-kind="folder">
                    <span class="kb-entry-main">
                        <span class="kb-entry-icon" aria-hidden="true">..</span>
                        <span class="kb-entry-name">Parent folder</span>
                    </span>
                    <span class="kb-entry-meta">Folder</span>
                </button>
            ` : "";

            const folders = data.folders.map((folder) => `
                <div class="kb-entry">
                    <button class="kb-entry-main" type="button" data-kb-path="${escapeHtml(folder.path)}" data-kb-kind="folder">
                        <span class="kb-entry-icon" aria-hidden="true">D</span>
                        <span class="kb-entry-name">${escapeHtml(folder.name)}</span>
                    </button>
                    <button class="kb-delete" type="button" data-kb-delete="${escapeHtml(folder.path)}" data-kb-delete-kind="folder" title="Delete folder">×</button>
                </div>
            `).join("");

            const files = data.files.map((file) => {
                const isIndexing = file.ingestion && file.ingestion.phase !== "complete" && file.ingestion.phase !== "failed";
                return `
                <div class="kb-entry${isIndexing ? " kb-entry-indexing" : ""}">
                    <div class="kb-entry-top">
                        <button class="kb-entry-main" type="button" data-kb-path="${escapeHtml(file.path)}" data-kb-kind="file">
                            <span class="kb-entry-icon" aria-hidden="true">T</span>
                            <span class="kb-entry-name">${escapeHtml(file.name)}</span>
                        </button>
                        <div style="display:flex;align-items:center;gap:8px;flex:0 0 auto;">
                            <span class="kb-entry-meta">${formatBytes(file.size || 0)}</span>
                            <button class="kb-delete" type="button" data-kb-delete="${escapeHtml(file.path)}" data-kb-delete-kind="file" title="Delete file">×</button>
                        </div>
                    </div>
                    ${renderFileProgress(file.ingestion)}
                </div>
            `;
            }).join("");

            if (!parentEntry && !folders && !files) {
                kbBrowser.innerHTML = `
                    <section class="kb-empty">
                        <h3>No files yet</h3>
                        <p>Create folders and upload documents to build this knowledge base.</p>
                    </section>
                `;
                return;
            }

            kbBrowser.innerHTML = parentEntry + folders + files;
            kbBrowser.querySelectorAll("[data-kb-kind='folder']").forEach((button) => {
                button.addEventListener("click", () => loadKnowledgeBase(button.dataset.kbPath || ""));
            });
            kbBrowser.querySelectorAll("[data-kb-kind='file']").forEach((button) => {
                button.addEventListener("click", () => loadDocumentChunks(button.dataset.kbPath || ""));
            });
            kbBrowser.querySelectorAll("[data-kb-delete]").forEach((button) => {
                button.addEventListener("click", (event) => {
                    event.stopPropagation();
                    deleteKnowledgeItem(button.dataset.kbDelete || "", button.dataset.kbDeleteKind || "file");
                });
            });
        }

        function renderDocumentChunks(data) {
            const chunks = data.chunks || [];
            const chunkCards = chunks.map((chunk, index) => `
                <article class="kb-chunk-card">
                    <header>Chunk ${index + 1}</header>
                    <pre>${escapeHtml(chunk.text)}</pre>
                </article>
            `).join("");

            kbBrowser.innerHTML = `
                <section class="kb-chunk-view">
                    <div class="kb-chunk-header">
                        <div class="kb-chunk-title">
                            <h3>${escapeHtml(data.source)}</h3>
                            <div class="kb-entry-meta">${chunks.length} chunks</div>
                        </div>
                        <button id="kb-back-to-folder" type="button">Back</button>
                    </div>
                    ${chunkCards || `
                        <section class="kb-empty">
                            <h3>No chunks found</h3>
                            <p>This document has not been indexed yet.</p>
                        </section>
                    `}
                </section>
            `;
            document.querySelector("#kb-back-to-folder").addEventListener("click", () => {
                renderKnowledgeBase();
                setKnowledgeStatus("");
            });
        }

        async function loadDocumentChunks(path) {
            setKnowledgeStatus("Loading chunks...");
            try {
                const response = await fetch(`/api/knowledge-base/files/chunks?path=${encodeURIComponent(path)}`);
                if (!response.ok) {
                    const data = await response.json().catch(() => ({ detail: "Could not load chunks." }));
                    throw new Error(data.detail || "Could not load chunks.");
                }
                renderDocumentChunks(await response.json());
                setKnowledgeStatus("");
            } catch (error) {
                setKnowledgeStatus(error.message, true);
            }
        }

        async function deleteKnowledgeItem(path, kind) {
            if (!confirm(`Delete this ${kind}?`)) {
                return;
            }

            setKnowledgeStatus("Deleting...");
            try {
                const response = await fetch(`/api/knowledge-base/${kind === "folder" ? "folders" : "files"}?path=${encodeURIComponent(path)}`, {
                    method: "DELETE"
                });
                if (!response.ok) {
                    const data = await response.json().catch(() => ({ detail: "Could not delete item." }));
                    throw new Error(data.detail || "Could not delete item.");
                }
                state.knowledgeBase = {
                    ...(await response.json()),
                    loaded: true
                };
                renderKnowledgeBase();
                setKnowledgeStatus("Deleted.");
            } catch (error) {
                setKnowledgeStatus(error.message, true);
            }
        }

        async function loadKnowledgeBase(path = "") {
            setKnowledgeStatus("Loading...");
            try {
                const response = await fetch(`/api/knowledge-base?path=${encodeURIComponent(path)}`);
                if (!response.ok) {
                    throw new Error("Could not load the knowledge base folder.");
                }
                const payload = await response.json();
                state.knowledgeBase = {
                    ...payload,
                    activeIngestions: mergeActiveIngestions(payload),
                    loaded: true
                };
                renderKnowledgeBase();
                setKnowledgeStatus("");

                if ((state.knowledgeBase.activeIngestions || []).length) {
                    ensureIngestionPolling();
                } else {
                    stopIngestionPolling();
                }
            } catch (error) {
                setKnowledgeStatus(error.message, true);
            }
        }

        async function createKnowledgeFolder(event) {
            event.preventDefault();
            const name = kbFolderName.value.trim();
            if (!name) {
                setKnowledgeStatus("Write a folder name first.", true);
                kbFolderName.focus();
                return;
            }

            setKnowledgeStatus("Creating folder...");
            try {
                const response = await fetch("/api/knowledge-base/folders", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ parent: state.knowledgeBase.path || "", name })
                });
                if (!response.ok) {
                    const data = await response.json().catch(() => ({ detail: "Could not create folder." }));
                    throw new Error(data.detail || "Could not create folder.");
                }
                state.knowledgeBase = {
                    ...(await response.json()),
                    loaded: true
                };
                kbFolderName.value = "";
                renderKnowledgeBase();
                setKnowledgeStatus("Folder created.");
            } catch (error) {
                setKnowledgeStatus(error.message, true);
            }
        }

        async function uploadKnowledgeFile(event) {
            event.preventDefault();
            const file = kbFile.files[0];
            if (!file) {
                setKnowledgeStatus("Choose a document first.", true);
                return;
            }
            const allowedExtensions = [".txt", ".md", ".pdf", ".docx"];
            if (!allowedExtensions.some((extension) => file.name.toLowerCase().endsWith(extension))) {
                setKnowledgeStatus("Supported files: .txt, .md, .pdf, .docx.", true);
                return;
            }

            const formData = new FormData();
            formData.append("parent", state.knowledgeBase.path || "");
            formData.append("file", file);

            setKnowledgeStatus(`Uploading ${file.name}...`);
            try {
                const response = await fetch("/api/knowledge-base/files", {
                    method: "POST",
                    body: formData
                });
                if (!response.ok) {
                    const data = await response.json().catch(() => ({ detail: "Could not upload file." }));
                    throw new Error(data.detail || "Could not upload file.");
                }

                const payload = await response.json();
                state.knowledgeBase = {
                    ...payload,
                    activeIngestions: mergeActiveIngestions(payload),
                    loaded: true
                };
                kbFile.value = "";
                renderKnowledgeBase();
                setKnowledgeStatus(`${file.name} uploaded. Each file shows its own chunking progress below.`);
                ensureIngestionPolling();
            } catch (error) {
                setKnowledgeStatus(error.message, true);
            }
        }
"""

KNOWLEDGE_BASE_EVENTS = """
        kbUpButton.addEventListener("click", () => loadKnowledgeBase(state.knowledgeBase.parent || ""));
        kbFolderForm.addEventListener("submit", createKnowledgeFolder);
        kbUploadForm.addEventListener("submit", uploadKnowledgeFile);
"""


def render_knowledge_menu_button() -> str:
    return """
            <button class="menu-button" type="button" data-menu="knowledge" aria-controls="knowledge-panel">
                <span class="menu-icon" aria-hidden="true">~</span>
                <span>Knowledge Base</span>
            </button>"""


def render_knowledge_panel() -> str:
    return """
            <section class="menu-panel" id="knowledge-panel" data-panel="knowledge">
                <section class="knowledge-base">
                    <header class="kb-header">
                        <div>
                            <h2>Knowledge Base</h2>
                            <div class="kb-path" id="kb-path">/</div>
                        </div>
                        <button id="kb-up" type="button">Up folder</button>
                    </header>

                    <section class="kb-tools">
                        <form class="kb-form" id="kb-folder-form">
                            <label for="kb-folder-name">Create folder</label>
                            <div class="kb-form-row">
                                <input class="kb-input" id="kb-folder-name" type="text" placeholder="Folder name">
                                <button type="submit">Create</button>
                            </div>
                        </form>

                        <form class="kb-form" id="kb-upload-form">
                            <label for="kb-file">Upload document</label>
                            <div class="kb-form-row">
                                <input class="kb-file-input" id="kb-file" type="file" accept=".txt,.md,.pdf,.docx,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document">
                                <button type="submit">Upload</button>
                            </div>
                        </form>
                    </section>

                    <section class="kb-content">
                        <div class="kb-browser" id="kb-browser"></div>
                        <div class="status" id="kb-status"></div>
                    </section>
                </section>
            </section>"""

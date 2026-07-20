import { useEffect, useState } from "react";
import {
  Folder, FileText, Upload, FolderPlus, ChevronRight,
  Home, Loader2, X, ChevronDown, AlertTriangle,
} from "lucide-react";
import clsx from "clsx";
import { kbApi } from "../services/api";
import type { KBFolder, KBFile, ChunkRecord, KBHealthPayload } from "../types";

function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function KnowledgeBase() {
  const [path, setPath] = useState("");
  const [parent, setParent] = useState("");
  const [folders, setFolders] = useState<KBFolder[]>([]);
  const [files, setFiles] = useState<KBFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [newFolder, setNewFolder] = useState("");
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [selectedFile, setSelectedFile] = useState<KBFile | null>(null);
  const [chunks, setChunks] = useState<ChunkRecord[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [health, setHealth] = useState<KBHealthPayload | null>(null);

  const loadPath = async (p: string) => {
    setLoading(true);
    setError("");
    try {
      const r = await kbApi.browse(p);
      setPath(r.data.path);
      setParent(r.data.parent);
      setFolders(r.data.folders);
      setFiles(r.data.files);
    } catch {
      setError("Failed to load folder");
    } finally {
      setLoading(false);
    }
  };

  const refreshHealth = () => {
    if (localStorage.getItem("token")) {
      kbApi.health().then((r) => setHealth(r.data)).catch(() => {/* non-fatal */});
    }
  };

  useEffect(() => {
    loadPath("");
    refreshHealth();
  }, []);

  const createFolder = async () => {
    if (!newFolder.trim()) return;
    await kbApi.createFolder(path, newFolder.trim());
    setNewFolder("");
    setShowNewFolder(false);
    await loadPath(path);
  };

  const uploadFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await kbApi.upload(path, file);
      await loadPath(path);
      refreshHealth();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Upload failed";
      setError(msg);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const openFile = async (file: KBFile) => {
    setSelectedFile(file);
    setChunksLoading(true);
    setChunks([]);
    try {
      const r = await kbApi.getChunks(file.path);
      setChunks(r.data.chunks);
    } catch {
      setChunks([]);
    } finally {
      setChunksLoading(false);
    }
  };

  const breadcrumbs = path
    ? ["", ...path.split("/").filter(Boolean)]
    : [""];

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Knowledge Base</h1>
          <p className="text-sm text-gray-400 mt-1">Documents indexed for the AI agent to search</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowNewFolder((v) => !v)}
            className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-3 py-1.5 rounded-lg transition-colors"
          >
            <FolderPlus size={14} />
            New folder
          </button>
          <label className={clsx(
            "flex items-center gap-1.5 text-sm text-white px-3 py-1.5 rounded-lg transition-colors cursor-pointer",
            uploading
              ? "bg-indigo-600/50 cursor-wait"
              : "bg-indigo-600 hover:bg-indigo-500"
          )}>
            {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
            Upload
            <input
              type="file"
              accept=".txt,.md,.pdf,.docx"
              className="hidden"
              onChange={uploadFile}
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {/* Degraded-docs alert banner */}
      {health && health.degraded_count > 0 && (
        <div className="mb-4 flex items-start gap-3 bg-amber-950 border border-amber-800 rounded-lg px-4 py-3">
          <AlertTriangle size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-amber-300">
              {health.degraded_count} {health.degraded_count === 1 ? "document" : "documents"} stored in FAISS fallback
            </p>
            <p className="text-xs text-amber-500 mt-0.5">
              Qdrant was unreachable during ingestion. Search quality may be degraded.
              Re-upload these documents once Qdrant is healthy to restore full-quality retrieval.
            </p>
          </div>
          <span className="text-xs font-mono text-amber-600 flex-shrink-0 mt-0.5">
            {health.degraded_count} degraded
          </span>
        </div>
      )}

      {/* Breadcrumb */}
      <div className="flex items-center gap-1 text-sm text-gray-500 mb-4">
        <button onClick={() => loadPath("")} className="hover:text-white flex items-center gap-1">
          <Home size={13} />
          Knowledge base
        </button>
        {path.split("/").filter(Boolean).map((seg, i, arr) => {
          const p = arr.slice(0, i + 1).join("/");
          return (
            <span key={p} className="flex items-center gap-1">
              <ChevronRight size={12} />
              <button onClick={() => loadPath(p)} className="hover:text-white">{seg}</button>
            </span>
          );
        })}
      </div>

      {/* New folder input */}
      {showNewFolder && (
        <div className="flex items-center gap-2 mb-4">
          <input
            type="text"
            value={newFolder}
            onChange={(e) => setNewFolder(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createFolder()}
            placeholder="Folder name..."
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-600"
          />
          <button
            onClick={createFolder}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-3 py-1.5 rounded-lg"
          >
            Create
          </button>
          <button onClick={() => setShowNewFolder(false)} className="text-gray-600 hover:text-gray-400">
            <X size={14} />
          </button>
        </div>
      )}

      {error && (
        <div className="mb-4 text-red-400 text-sm bg-red-950 border border-red-900 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-gray-500 text-sm flex items-center gap-2">
          <Loader2 size={14} className="animate-spin" /> Loading...
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          {parent !== "" && parent !== undefined && (
            <button
              onClick={() => loadPath(parent)}
              className="flex items-center gap-3 px-5 py-3 w-full text-left hover:bg-gray-800 border-b border-gray-800 text-gray-400 text-sm transition-colors"
            >
              <Folder size={16} className="text-gray-600" />
              ..
            </button>
          )}

          {folders.map((f) => (
            <button
              key={f.path}
              onClick={() => loadPath(f.path)}
              className="flex items-center gap-3 px-5 py-3 w-full text-left hover:bg-gray-800 border-b border-gray-800 transition-colors"
            >
              <Folder size={16} className="text-yellow-500" />
              <span className="text-sm text-white">{f.name}</span>
            </button>
          ))}

          {files.map((f) => (
            <button
              key={f.path}
              onClick={() => openFile(f)}
              className={clsx(
                "flex items-center justify-between px-5 py-3 w-full text-left border-b border-gray-800 last:border-0 transition-colors",
                selectedFile?.path === f.path
                  ? "bg-indigo-600/10 border-l-2 border-l-indigo-600"
                  : "hover:bg-gray-800"
              )}
            >
              <div className="flex items-center gap-3">
                <FileText size={16} className="text-indigo-400 flex-shrink-0" />
                <span className="text-sm text-white">{f.name}</span>
              </div>
              <span className="text-xs text-gray-600">{fileSize(f.size)}</span>
            </button>
          ))}

          {folders.length === 0 && files.length === 0 && (
            <div className="px-5 py-10 text-center text-gray-600 text-sm">
              This folder is empty — upload a document to get started.
            </div>
          )}
        </div>
      )}

      {/* Chunk inspector */}
      {selectedFile && (
        <div className="mt-6 bg-gray-900 border border-gray-800 rounded-xl">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
            <div>
              <p className="text-sm font-medium text-white">{selectedFile.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {chunksLoading ? "Loading chunks..." : `${chunks.length} indexed chunks`}
              </p>
            </div>
            <button
              onClick={() => { setSelectedFile(null); setChunks([]); }}
              className="text-gray-600 hover:text-gray-400"
            >
              <X size={14} />
            </button>
          </div>

          {chunksLoading ? (
            <div className="px-5 py-6 text-gray-500 text-sm flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" /> Loading chunks...
            </div>
          ) : (
            <div className="divide-y divide-gray-800 max-h-96 overflow-y-auto">
              {chunks.map((c) => (
                <ChunkRow key={c.id} chunk={c} />
              ))}
              {chunks.length === 0 && (
                <div className="px-5 py-6 text-gray-600 text-sm">No chunks found for this document.</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ChunkRow({ chunk }: { chunk: ChunkRecord }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="px-5 py-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 w-full text-left"
      >
        <span className="text-xs text-gray-600 font-mono w-8">#{chunk.chunk}</span>
        <span className="flex-1 text-xs text-gray-400 truncate">{chunk.text.slice(0, 80)}</span>
        {open ? <ChevronDown size={12} className="text-gray-600" /> : <ChevronRight size={12} className="text-gray-600" />}
      </button>
      {open && (
        <div className="mt-2 ml-10 bg-gray-800 rounded-lg p-3 text-xs text-gray-300 whitespace-pre-wrap">
          {chunk.text}
        </div>
      )}
    </div>
  );
}

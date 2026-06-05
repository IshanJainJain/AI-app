# RAG System Structure

This app has a local Retrieval-Augmented Generation path for the Knowledge Base. Documents are uploaded through the UI, parsed into text, chunked, embedded with Ollama, stored in FAISS/BM25 indexes, retrieved during chat, and injected into the final prompt sent to the local chat model.

The whole path is designed to stay local when Ollama runs on the same VM.

## High-Level Flow

```text
User uploads document
  -> FastAPI Knowledge Base route
  -> File validation and save under knowledge_base/
  -> Text parsing
  -> Recursive chunking
  -> Optional agentic chunk refinement with Ollama /api/generate
  -> Embedding with Ollama /api/embeddings
  -> FAISS vector index update
  -> BM25 keyword index update
  -> chunks.json metadata update

User sends chat prompt
  -> FastAPI chat route
  -> Query embedding
  -> FAISS semantic search
  -> BM25 keyword search
  -> Candidate merge
  -> Optional reranking
  -> Context selection
  -> Prompt assembly
  -> Ollama /api/generate chat answer
  -> Thread history saved in history.db
```

## Repository Structure

```text
AI-app/
  main.py
  templates.py
  knowledge_base_api.py
  knowledge_base_templates.py
  rag_config.py
  rag_parsing.py
  rag_chunking.py
  rag_embedding.py
  rag_store.py
  rag_retrieval.py
  rag_ingestion.py
  rag_reindex.py
  DATABASE.py
  history.db
  requirements.txt
  .env.example
  .gitignore
  RAG.md

  knowledge_base/                 Runtime only, git-ignored
    uploaded-file.pdf
    folder/
      uploaded-file.docx
    .vector_store/
      faiss.index
      chunks.json
      bm25.pkl
    agentic_chunk_interactions.jsonl
```

`knowledge_base/` may not exist in a fresh checkout. It is created at app startup by `init_knowledge_base()`.

## Python File Responsibilities

### `main.py`

Owns the chat application and FastAPI app setup.

Key responsibilities:

- Creates the `FastAPI` app.
- Includes the Knowledge Base router from `knowledge_base_api.py`.
- Initializes SQLite and the Knowledge Base folder on startup.
- Serves the main HTML UI.
- Handles conversation/thread API routes.
- Calls `retrieve_context()` before each LLM answer.
- Builds the final prompt with global context, thread history, retrieved chunks, and the latest user question.
- Calls the configured Ollama generation endpoint.

Important routes:

```text
GET  /
GET  /api/global-context
PUT  /api/global-context
GET  /api/threads
POST /api/threads
GET  /api/threads/{thread_id}
PATCH /api/threads/{thread_id}
POST /api/threads/{thread_id}/prompt
```

### `templates.py`

Builds the main HTML/CSS/JavaScript for the chat UI.

Key responsibilities:

- Renders the chat layout.
- Renders thread list, messages, rename controls, prompt composer, and global context editor.
- Sends prompt requests to `/api/threads/{thread_id}/prompt`.
- Shows progress messages while retrieval and local generation are running.
- Injects Knowledge Base UI fragments from `knowledge_base_templates.py`.

### `knowledge_base_api.py`

Owns Knowledge Base HTTP routes and file safety.

Key responsibilities:

- Creates `knowledge_base/` at startup.
- Validates folder/file names.
- Prevents path traversal outside `knowledge_base/`.
- Lists folders and files.
- Creates folders.
- Uploads supported documents.
- Calls `ingest_document()` after upload.
- Deletes uploaded files/folders.
- Returns stored chunks for a document.

Important routes:

```text
GET    /api/knowledge-base
GET    /api/knowledge-base/files/chunks
POST   /api/knowledge-base/folders
POST   /api/knowledge-base/files
DELETE /api/knowledge-base/files
DELETE /api/knowledge-base/folders
```

### `knowledge_base_templates.py`

Builds the Knowledge Base UI embedded in the main page.

Key responsibilities:

- Renders the Knowledge Base menu button and panel.
- Handles folder navigation.
- Handles document upload.
- Shows upload/indexing status.
- Shows chunks for a selected document.
- Calls Knowledge Base API routes from browser JavaScript.

### `rag_config.py`

Central configuration for RAG behavior.

Key responsibilities:

- Defines supported document extensions.
- Reads Ollama embedding and chunking endpoints from environment variables.
- Reads chunking sizes, timeouts, retrieval limits, reranker settings, and context token limits.
- Defines vector store filenames.

### `rag_parsing.py`

Converts uploaded document bytes into plain text.

Supported formats:

- `.txt`
- `.md`
- `.pdf`
- `.docx`

Parsing libraries:

- `.pdf` uses `pypdf`.
- `.docx` uses `python-docx`.
- `.txt` and `.md` decode as UTF-8 with replacement.

Scanned image-only PDFs usually produce little or no text because OCR is not implemented.

### `rag_chunking.py`

Splits parsed text into chunks.

Key responsibilities:

- Normalizes whitespace.
- Creates deterministic recursive chunks first.
- Optionally refines each chunk window with a local Ollama generation model.
- Parses strict JSON from the chunking model.
- Falls back to deterministic chunks when the model times out or returns malformed JSON.
- Logs agentic chunk interactions to `knowledge_base/agentic_chunk_interactions.jsonl`.

Recursive splitter separators:

```python
["\n\n", "\n", ". ", " ", ""]
```

Expected agentic chunk response shape:

```json
{"final_chunks": ["complete chunk"], "carryover": ["trailing chunk"]}
```

### `rag_embedding.py`

Embeds chunks and user queries with Ollama.

Key responsibilities:

- Calls `OLLAMA_EMBED_URL`.
- Uses `OLLAMA_EMBED_MODEL`.
- Sends one chunk/query per embedding request.
- Returns embedding vectors as lists of floats.

Default endpoint:

```text
http://localhost:11434/api/embeddings
```

### `rag_store.py`

Stores and searches retrieval indexes.

Key responsibilities:

- Loads and writes `chunks.json`.
- Creates/appends FAISS vectors.
- Normalizes vectors before storage.
- Builds and saves the BM25 keyword index.
- Searches FAISS.
- Searches BM25.
- Deduplicates chunk identities.
- Optionally reranks candidate chunks with `FlagEmbedding`.
- Selects retrieved context under a token budget.
- Formats selected chunks for prompt injection.

Stored index files:

```text
knowledge_base/.vector_store/faiss.index
knowledge_base/.vector_store/chunks.json
knowledge_base/.vector_store/bm25.pkl
```

### `rag_retrieval.py`

Defines the chat-time retrieval path used by `main.py`.

Key responsibilities:

- Runs FAISS semantic search.
- Runs BM25 keyword search.
- Merges and deduplicates candidates.
- Applies optional reranking.
- Selects chunks under `MAX_CONTEXT_TOKENS`.
- Returns formatted context text for the final chat prompt.

This is the retrieval module imported by `main.py`.

### `rag_ingestion.py`

Coordinates document ingestion.

Key responsibilities:

- Parses uploaded files with `parse_document()`.
- Chunks text with `split_text()`.
- Embeds chunks with `embed_chunks()`.
- Stores vectors and metadata with `store_vectors()`.
- Returns indexing metadata to the upload route.

### `rag_reindex.py`

Rebuild helper for Knowledge Base indexes.

Key responsibilities:

- Re-reads documents from `knowledge_base/`.
- Re-parses, re-chunks, re-embeds, and re-stores indexes.
- Useful after changing embedding model, chunking strategy, or index files.

### `DATABASE.py`

Stores non-RAG chat state in SQLite.

Key responsibilities:

- Creates and migrates `history.db`.
- Stores global context.
- Stores threads and messages.
- Provides thread/message CRUD helpers.
- Generates a short thread title from the first prompt.

## Runtime Storage

### Source Documents

Uploaded source documents are saved under:

```text
knowledge_base/
```

Example:

```text
knowledge_base/hr/leave-policy.pdf
```

### Vector Store

RAG indexes are saved under:

```text
knowledge_base/.vector_store/
```

Files:

```text
faiss.index   Binary FAISS vector index
chunks.json   Raw chunk text and metadata
bm25.pkl      Pickled BM25 keyword index
```

### Chunk Metadata Shape

`chunks.json` contains records like:

```json
{
  "id": 0,
  "text": "chunk text...",
  "metadata": {
    "source": "folder/policy.pdf",
    "chunk": 0,
    "sha256": "document hash",
    "embedding_model": "nomic-embed-text"
  }
}
```

The `source` field connects stored chunks back to the uploaded document. The UI uses it when showing chunks for a clicked document.

### Agentic Chunk Log

Agentic chunking interactions are appended to:

```text
knowledge_base/agentic_chunk_interactions.jsonl
```

Each line records the model, source document, input window, raw response, and parsed output/error. This is useful when diagnosing bad chunking.

## Ingestion Flow

### 1. Upload Validation

Implemented in `knowledge_base_api.py`.

The upload route:

```text
POST /api/knowledge-base/files
```

Validates:

- Parent folder exists.
- Filename is safe.
- Extension is supported.
- File size is below `MAX_DOCUMENT_BYTES`.
- No file/folder already exists with the same name.

Allowed filename characters:

```text
letters, numbers, spaces, dots, underscores, hyphens
```

Path traversal is blocked by resolving paths and ensuring they stay inside `knowledge_base/`.

### 2. Parsing

Implemented in `rag_parsing.py`.

The parser converts uploaded document bytes into plain text. If no text can be extracted, ingestion fails and the uploaded file is removed so the UI does not show an unindexed document.

### 3. Recursive Chunking

Implemented in `rag_chunking.py`.

The text is normalized and split with the deterministic recursive splitter using:

```text
RAG_CHUNK_SIZE=360
RAG_CHUNK_OVERLAP=0
```

These recursive chunks are the stable fallback and the input to the agentic refinement step.

### 4. Agentic Chunk Refinement

Implemented in `agentic_refine_chunk_window()` in `rag_chunking.py`.

The app sends a small window of recursive chunks to Ollama:

```text
POST http://localhost:11434/api/generate
```

Default configured model:

```text
AGENTIC_CHUNK_MODEL=gemma3:1b
```

For the VM setup used here, the intended model is:

```text
AGENTIC_CHUNK_MODEL=ministral-3:latest
```

The model is asked to preserve exact wording, combine related clauses, split oversized text, and return strict JSON.

If the model fails, times out, or returns malformed JSON, that window falls back to the deterministic recursive chunks.

### 5. Embedding

Implemented in `rag_embedding.py`.

Each final chunk is sent to Ollama:

```text
POST http://localhost:11434/api/embeddings
```

Default model:

```text
nomic-embed-text
```

### 6. FAISS and BM25 Storage

Implemented in `rag_store.py`.

The pipeline:

1. Converts embeddings to `float32`.
2. L2-normalizes vectors with `faiss.normalize_L2`.
3. Stores vectors in `faiss.IndexFlatIP`.
4. Appends vectors to the existing index.
5. Appends chunk records to `chunks.json`.
6. Rebuilds and saves `bm25.pkl`.

Because vectors are normalized and stored in `IndexFlatIP`, inner product behaves like cosine similarity.

## Retrieval Flow

### 1. Chat Prompt Received

Implemented in `main.py`.

The route:

```text
POST /api/threads/{thread_id}/prompt
```

loads previous messages, then calls:

```python
retrieve_context(prompt, KNOWLEDGE_BASE_DIR, MAX_CONTEXT_TOKENS)
```

Retrieval is wrapped in a timeout controlled by:

```text
RAG_RETRIEVAL_TIMEOUT_SECONDS=30
```

If retrieval fails or times out, the app still answers without Knowledge Base context.

### 2. FAISS Semantic Search

Implemented in `faiss_search()` in `rag_store.py`.

Steps:

1. Embed the user query with `embed_query()`.
2. Load `faiss.index`.
3. Normalize the query vector.
4. Search the top `RAG_TOP_K` vector matches.
5. Read matching chunk text/metadata from `chunks.json`.

### 3. BM25 Keyword Search

Implemented in `bm25_search()` in `rag_store.py`.

Steps:

1. Tokenize the user query.
2. Load `bm25.pkl`.
3. Score stored chunks with BM25.
4. Return the top `RAG_TOP_K` keyword matches.

### 4. Candidate Merge

Implemented in `hybrid_retrieval()` in `rag_retrieval.py`.

FAISS and BM25 results are concatenated, deduplicated by source/chunk/text identity, and trimmed to `RAG_TOP_K`.

### 5. Optional Reranking

Implemented in `rerank_chunks()` in `rag_store.py`.

Reranking is disabled by default:

```text
RERANKER_ENABLED=0
```

Reason:

`FlagEmbedding` reranker loading can be slow on small VMs and can make the frontend appear stuck during chat. Enable it only when the reranker model is already available and the VM has enough CPU/RAM.

Enable with:

```bash
RERANKER_ENABLED=1 RERANKER_MODEL=BAAI/bge-reranker-base
```

### 6. Context Selection

Implemented in `select_context()` in `rag_store.py`.

The selected chunks are capped by:

```text
MAX_CONTEXT_TOKENS=6000
```

Token counting uses `tiktoken` when available, with a character-count fallback.

### 7. Prompt Injection

Implemented in `build_context_prompt()` in `main.py`.

The final prompt contains:

1. Global context.
2. Current thread history.
3. Retrieved Knowledge Base chunks.
4. Latest user question.

The assistant is instructed to prioritize the latest question and Knowledge Base chunks, avoid invented facts, and answer conservatively if sources conflict.

## Configuration

### Chat Model

```text
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=devstral
LLM_TIMEOUT_SECONDS=20
```

Recommended VM override for this setup:

```text
OLLAMA_MODEL=ministral-3:latest
LLM_TIMEOUT_SECONDS=300
```

### Embedding

```text
OLLAMA_EMBED_URL=http://localhost:11434/api/embeddings
OLLAMA_EMBED_MODEL=nomic-embed-text
EMBED_TIMEOUT_SECONDS=120
```

Changing the embedding model after vectors already exist can create dimension mismatches or mixed embedding spaces. If you change `OLLAMA_EMBED_MODEL`, rebuild `knowledge_base/.vector_store/`.

### Agentic Chunking

```text
OLLAMA_AGENTIC_CHUNK_URL=http://localhost:11434/api/generate
AGENTIC_CHUNK_MODEL=gemma3:1b
AGENTIC_CHUNK_TIMEOUT_SECONDS=300
AGENTIC_CHUNK_WINDOW_SIZE=5
AGENTIC_CHUNK_TARGET_CHARS=360
AGENTIC_CHUNK_MAX_CHARS=1800
```

Recommended VM override for this setup:

```text
AGENTIC_CHUNK_MODEL=ministral-3:latest
```

### Recursive Chunking

```text
RAG_CHUNK_SIZE=360
RAG_CHUNK_OVERLAP=0
```

`AGENTIC_CHUNK_TARGET_CHARS` defaults to `RAG_CHUNK_SIZE` unless explicitly set.

### Retrieval

```text
RAG_RETRIEVAL_TIMEOUT_SECONDS=30
RAG_TOP_K=8
MAX_CONTEXT_TOKENS=6000
RERANKER_ENABLED=0
RERANKER_MODEL=bge-reranker-base
RERANKER_DEVICE=cpu
```

### Uploads

```text
MAX_DOCUMENT_BYTES=52428800
```

That is 50 MB.

## VM Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Pull the local models:

```bash
ollama pull ministral-3:latest
ollama pull nomic-embed-text
```

Run the app:

```bash
OLLAMA_URL=http://localhost:11434/api/generate \
OLLAMA_MODEL='ministral-3:latest' \
LLM_TIMEOUT_SECONDS=300 \
OLLAMA_AGENTIC_CHUNK_URL=http://localhost:11434/api/generate \
AGENTIC_CHUNK_MODEL='ministral-3:latest' \
OLLAMA_EMBED_URL=http://localhost:11434/api/embeddings \
OLLAMA_EMBED_MODEL='nomic-embed-text' \
RAG_RETRIEVAL_TIMEOUT_SECONDS=30 \
RAG_TOP_K=8 \
RERANKER_ENABLED=0 \
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://<VM_IP_ADDRESS>:8000
```

## Reindexing

Reindex when:

- The embedding model changes.
- The chunking strategy changes.
- `faiss.index`, `chunks.json`, or `bm25.pkl` is missing/corrupt.
- Documents were manually copied into `knowledge_base/`.

Use `rag_reindex.py` as the rebuild helper. It reparses documents, rechunks text, regenerates embeddings, and rebuilds the vector/keyword indexes.

## Troubleshooting

### Frontend Stays Loading

Likely causes:

- Ollama generation is slow on the VM.
- Query embedding is slow or Ollama embedding endpoint is unavailable.
- Reranker was enabled and is loading/running slowly.
- The chat model context is too large.

Useful settings:

```bash
RAG_RETRIEVAL_TIMEOUT_SECONDS=30
RAG_TOP_K=8
RERANKER_ENABLED=0
LLM_TIMEOUT_SECONDS=300
```

The backend logs retrieval timing and total prompt timing.

### Upload Succeeds Slowly

Likely causes:

- Large document.
- Many chunks.
- Slow agentic chunking model.
- Slow embedding model.

Useful settings:

```bash
AGENTIC_CHUNK_WINDOW_SIZE=5
AGENTIC_CHUNK_TIMEOUT_SECONDS=300
EMBED_TIMEOUT_SECONDS=120
```

For faster but less semantic ingestion, reduce model use by relying more on deterministic chunking.

### No Knowledge Context Retrieved

Check:

- `knowledge_base/.vector_store/faiss.index` exists.
- `knowledge_base/.vector_store/chunks.json` exists.
- `knowledge_base/.vector_store/bm25.pkl` exists.
- Ollama embedding endpoint is running.
- `OLLAMA_EMBED_MODEL` matches the model used to build the index.

### Embedding Dimension Mismatch

This usually means the embedding model changed after vectors were already stored.

Fix:

1. Stop the app.
2. Rebuild the vector store with one embedding model.
3. Restart the app with the same `OLLAMA_EMBED_MODEL`.

## Security Notes

- `knowledge_base/` is git-ignored.
- `chunks.json` stores raw source text. Treat it as sensitive.
- `faiss.index` can encode sensitive information indirectly. Treat it as sensitive.
- `bm25.pkl` contains tokenized/indexed source text. Treat it as sensitive.
- All parsing, embedding, vector storage, and generation stay local only if Ollama URLs point to trusted local infrastructure.
- Do not point `OLLAMA_EMBED_URL` or `OLLAMA_AGENTIC_CHUNK_URL` at remote servers unless those servers are approved to receive confidential documents.

## Dependency List

Runtime dependencies are listed in `requirements.txt`:

```text
faiss-cpu
fastapi
httpx
numpy
pypdf
python-multipart
python-docx
rank-bm25
FlagEmbedding
tiktoken
uvicorn
```

`FlagEmbedding` is installed but inactive unless `RERANKER_ENABLED=1`.

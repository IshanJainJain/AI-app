# RAG Ingestion Pipeline

This project has a local Retrieval-Augmented Generation ingestion path for the Knowledge Base. The current work covers ingestion, chunk storage, FAISS vector storage, and chunk inspection from the UI. Retrieval into chat answers can be added on top of the same FAISS index later.

## What Is Done

When a user uploads a document in the Knowledge Base:

1. The FastAPI upload route receives the file.
2. The file is validated for name, type, size, and target folder.
3. The file is written into `knowledge_base/`.
4. The document is parsed into plain text.
5. The text is split into overlapping chunks.
6. Each chunk is embedded with a local Ollama embedding model.
7. The embeddings are normalized and appended to a FAISS index.
8. Chunk text and metadata are written to JSON alongside the FAISS index.
9. The upload returns success only after indexing succeeds.
10. If ingestion fails, the uploaded file is deleted so the file list does not show an unindexed document.

This is intentionally synchronous per upload. The app does not wait for a batch job that vectorizes all documents together. Each newly uploaded document is ingested immediately and incrementally appended to the vector database.

## Files Involved

- `knowledge_base_api.py`
  - Defines Knowledge Base API routes.
  - Handles folder browsing, folder creation, upload validation, and document chunk lookup.
  - Calls the ingestion pipeline after saving each uploaded document.

- `rag_ingestion.py`
  - Parses uploaded files.
  - Splits text into chunks.
  - Calls Ollama embeddings.
  - Stores vectors in FAISS.
  - Stores chunk text and metadata in JSON.
  - Reads chunks back for the Knowledge Base document viewer.

- `knowledge_base_templates.py`
  - Adds the Knowledge Base UI.
  - Uploads documents.
  - Lets users click documents and inspect all chunks for that document.

- `knowledge_base/`
  - Runtime-only local document storage.
  - Ignored by git because it may contain company policies, secrets, and embeddings.

## Supported Documents

The uploader currently supports:

- `.txt`
- `.md`
- `.pdf`
- `.docx`

Parsing behavior:

- `.txt` and `.md` are decoded as UTF-8 with replacement for invalid characters.
- `.pdf` is parsed with `pypdf.PdfReader`.
- `.docx` is parsed with `python-docx`.

Scanned PDFs that contain only images will usually produce little or no text. OCR is not implemented yet.

## Storage Layout

Uploaded source documents are saved under:

```text
knowledge_base/
```

The vector database and chunk metadata are saved under:

```text
knowledge_base/.vector_store/faiss.index
knowledge_base/.vector_store/chunks.json
```

`faiss.index` contains the vector embeddings.

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

The `source` field connects chunks back to the original uploaded document. The Knowledge Base UI uses this to show all chunks when a document is clicked.

## Ingestion Details

### 1. Upload Validation

Implemented in `knowledge_base_api.py`.

The upload route:

```text
POST /api/knowledge-base/files
```

Validates:

- parent folder exists
- filename is safe
- extension is supported
- file size is below the configured maximum
- no file/folder already exists with the same name

Allowed filename characters:

```text
letters, numbers, spaces, dots, underscores, hyphens
```

Path traversal is blocked by resolving paths and ensuring they stay inside `knowledge_base/`.

### 2. Parsing

Implemented in `parse_document()` in `rag_ingestion.py`.

The parser converts each uploaded document into plain text. If no text can be extracted, ingestion fails.

### 3. Chunking

Implemented in `split_text()` and `recursive_split()` in `rag_ingestion.py`.

The splitter is a local recursive character splitter inspired by `RecursiveCharacterTextSplitter`. It tries separators in this order:

```python
["\n\n", "\n", ". ", " ", ""]
```

This means it prefers to preserve:

1. paragraphs
2. lines
3. sentence-ish boundaries
4. word boundaries
5. raw character windows as a final fallback

After recursive splitting, adjacent pieces are merged up to the configured chunk size, and overlap is carried from the previous chunk into the next chunk.

### 4. Embedding

Implemented in `embed_chunks()` in `rag_ingestion.py`.

Each chunk is sent to Ollama:

```text
POST http://localhost:11434/api/embeddings
```

Default model:

```text
nomic-embed-text
```

This keeps company policy documents local to the VM, assuming Ollama is running locally there.

### 5. FAISS Storage

Implemented in `store_vectors()` in `rag_ingestion.py`.

The pipeline:

1. Converts embeddings to `float32`.
2. L2-normalizes vectors with `faiss.normalize_L2`.
3. Stores vectors in `faiss.IndexFlatIP`.
4. Appends new vectors to the existing index.
5. Writes the updated index to `faiss.index`.
6. Appends chunk records to `chunks.json`.

Because vectors are normalized and stored in `IndexFlatIP`, inner product behaves like cosine similarity.

## Hyperparameters

### `OLLAMA_EMBED_URL`

Default:

```text
http://localhost:11434/api/embeddings
```

Purpose:
Controls where embedding requests are sent.

Why this default:
It matches local Ollama and keeps documents inside the VM/local machine.

Impact of changing:
- Pointing to a remote URL may expose confidential documents to another machine.
- Pointing to a faster local Ollama server can improve ingestion speed.

### `OLLAMA_EMBED_MODEL`

Default:

```text
nomic-embed-text
```

Purpose:
Controls which embedding model creates vectors.

Why this default:
`nomic-embed-text` is a common local embedding model supported by Ollama, good enough for general document retrieval, and practical for VM/local use.

Impact of changing:
- Better embedding models can improve retrieval quality.
- Larger models may slow ingestion.
- Changing the model after vectors already exist can cause dimension mismatches or mixed embedding spaces.
- If you change the embedding model, it is safest to rebuild `knowledge_base/.vector_store/`.

### `EMBED_TIMEOUT_SECONDS`

Default:

```text
120
```

Purpose:
Maximum time allowed for embedding requests.

Why this default:
Large policy documents can create many chunks, and local embedding models may be slow on CPU-only VMs.

Impact of changing:
- Higher values reduce timeout failures on slow machines.
- Lower values fail faster when Ollama is stuck or unavailable.

### `RAG_CHUNK_SIZE`

Default:

```text
1200
```

Purpose:
Maximum target size for text chunks, measured in characters.

Why this default:
It is large enough to preserve meaningful policy context but small enough to keep embeddings focused. Policy documents often contain clauses, exceptions, and definitions that need nearby context.

Impact of changing:
- Smaller chunks:
  - More precise retrieval.
  - More chunks and embeddings.
  - More storage and slower ingestion.
  - Higher risk of losing context around a policy clause.
- Larger chunks:
  - Better context preservation.
  - Fewer embeddings and faster ingestion.
  - Retrieval may become less precise because each vector represents broader text.

### `RAG_CHUNK_OVERLAP`

Default:

```text
200
```

Purpose:
Number of characters copied from the previous chunk into the next chunk.

Why this default:
Overlap helps preserve continuity when a rule, definition, or exception crosses a chunk boundary.

Impact of changing:
- Higher overlap:
  - Better boundary continuity.
  - More duplicated text.
  - More embedding cost and storage.
- Lower overlap:
  - Less duplication.
  - Faster ingestion.
  - Higher chance of splitting important context across chunks.

### `MAX_DOCUMENT_BYTES`

Default:

```text
52428800
```

That is 50 MB.

Purpose:
Maximum allowed upload size.

Why this default:
Company policy PDFs and DOCX files can be large, but this prevents accidentally uploading extremely large files that make ingestion slow or unstable.

Impact of changing:
- Higher values allow larger documents but increase memory, parsing, and embedding load.
- Lower values protect the VM from heavy uploads but may reject legitimate policy bundles.

### `VECTOR_STORE_NAME`

Default:

```text
.vector_store
```

Purpose:
Directory name under `knowledge_base/` where FAISS and chunk metadata are stored.

Why this default:
The leading dot keeps vector internals visually separate from user-created folders.

Impact of changing:
Changing this path makes the app look for a different vector store. Existing indexed documents will not be found unless moved or rebuilt.

## Why FAISS `IndexFlatIP`

The current index type is:

```python
faiss.IndexFlatIP
```

Vectors are normalized before insertion, so inner product approximates cosine similarity.

Why this choice:

- Simple and reliable.
- Good for a first local RAG implementation.
- No training step.
- Exact search rather than approximate search.
- Easy to append new documents incrementally.

Impact:

- Retrieval quality is straightforward and predictable.
- Search can become slower as the corpus gets very large because it is exact search.
- For very large knowledge bases, consider approximate FAISS indexes such as IVF or HNSW.

## Current Limitation

The pipeline currently ingests and stores vectors, and the UI can inspect chunks per document.

It does not yet inject retrieved chunks into chat prompts. To complete full RAG answering, the next step would be:

1. Embed the user query.
2. Search `faiss.index`.
3. Read matching chunk text from `chunks.json`.
4. Add the top chunks into `build_context_prompt()` before calling the chat model.

## Security Notes

- `knowledge_base/` is git-ignored.
- All parsing, embedding, and vector storage are local if Ollama runs locally.
- Do not point `OLLAMA_EMBED_URL` at a remote server unless that server is approved to receive confidential company data.
- `chunks.json` stores raw text chunks, not just vectors. Treat it as sensitive.
- `faiss.index` may encode sensitive information indirectly. Treat it as sensitive too.

## VM Setup

Install dependencies:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Pull the embedding model:

```bash
ollama pull nomic-embed-text
```

Example run command:

```bash
OLLAMA_URL=http://localhost:11434/api/generate \
OLLAMA_MODEL='gemma3:1b' \
LLM_TIMEOUT_SECONDS=300 \
OLLAMA_EMBED_MODEL=nomic-embed-text \
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

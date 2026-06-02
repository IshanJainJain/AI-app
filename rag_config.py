import os

SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}

OLLAMA_EMBED_URL = os.getenv("OLLAMA_EMBED_URL", "http://localhost:11434/api/embeddings")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT_SECONDS = float(os.getenv("EMBED_TIMEOUT_SECONDS", "120"))
OLLAMA_CHUNK_URL = os.getenv("OLLAMA_AGENTIC_CHUNK_URL", "http://localhost:11434/api/generate")
AGENTIC_CHUNK_MODEL = os.getenv("AGENTIC_CHUNK_MODEL", "gemma3:1b")
AGENTIC_CHUNK_TIMEOUT_SECONDS = float(os.getenv("AGENTIC_CHUNK_TIMEOUT_SECONDS", "300"))
AGENTIC_CHUNK_TARGET_CHARS = int(os.getenv("AGENTIC_CHUNK_TARGET_CHARS", os.getenv("RAG_CHUNK_SIZE", "360")))
AGENTIC_CHUNK_MAX_CHARS = int(os.getenv("AGENTIC_CHUNK_MAX_CHARS", "1800"))
AGENTIC_CHUNK_WINDOW_SIZE = int(os.getenv("AGENTIC_CHUNK_WINDOW_SIZE", "5"))
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "360"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "0"))
VECTOR_STORE_NAME = ".vector_store"
AGENTIC_CHUNK_INTERACTION_LOG = "agentic_chunk_interactions.jsonl"
BM25_INDEX_NAME = "bm25.pkl"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "bge-reranker-base")
RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "cpu")
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "6000"))

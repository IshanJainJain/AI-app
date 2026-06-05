#!/bin/bash

export OLLAMA_URL="http://localhost:11434/api/generate"
export OLLAMA_MODEL="ministral-3:latest"
export LLM_TIMEOUT_SECONDS=300

export OLLAMA_AGENTIC_CHUNK_URL="http://localhost:11434/api/generate"
export AGENTIC_CHUNK_MODEL="ministral-3:latest"

export OLLAMA_EMBED_URL="http://localhost:11434/api/embeddings"
export OLLAMA_EMBED_MODEL="nomic-embed-text"

export RAG_RETRIEVAL_TIMEOUT_SECONDS=30
export RAG_TOP_K=8
export RERANKER_ENABLED=0

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
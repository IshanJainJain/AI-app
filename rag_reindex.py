import shutil
from pathlib import Path

from rag_chunking import split_text
from rag_config import SUPPORTED_DOCUMENT_EXTENSIONS
from rag_embedding import embed_chunks
from rag_parsing import parse_document
from rag_store import store_vectors


async def rebuild_knowledge_base_indexes(knowledge_base_dir: Path):
    vector_store_dir = knowledge_base_dir / ".vector_store"
    if vector_store_dir.exists():
        shutil.rmtree(vector_store_dir)

    documents = []
    for path in sorted(knowledge_base_dir.rglob("*")):
        if not path.is_file():
            continue
        if ".vector_store" in path.parts:
            continue
        if path.suffix.lower() not in SUPPORTED_DOCUMENT_EXTENSIONS:
            continue
        documents.append(path)

    for document_path in documents:
        relative_path = document_path.relative_to(knowledge_base_dir).as_posix()
        content = document_path.read_bytes()
        text = parse_document(document_path.name, content)
        chunks = await split_text(text, knowledge_base_dir, relative_path)
        if not chunks:
            continue
        vectors = await embed_chunks(chunks, background=True)
        store_vectors(knowledge_base_dir, relative_path, chunks, vectors, content)

import json
from pathlib import Path

import httpx

from rag_config import (
    AGENTIC_CHUNK_INTERACTION_LOG,
    AGENTIC_CHUNK_MAX_CHARS,
    AGENTIC_CHUNK_MODEL,
    AGENTIC_CHUNK_TARGET_CHARS,
    AGENTIC_CHUNK_TIMEOUT_SECONDS,
    AGENTIC_CHUNK_WINDOW_SIZE,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    OLLAMA_CHUNK_URL,
    VECTOR_STORE_NAME,
)


async def split_text(
    text: str,
    knowledge_base_dir: Path,
    relative_path: str,
    on_progress=None,
) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    base_chunks = fallback_split_text(normalized, CHUNK_SIZE, CHUNK_OVERLAP)
    if not base_chunks:
        return []

    interaction_log_path = agentic_chunk_log_path(knowledge_base_dir)
    refined_chunks = []
    carryover = []
    total_base_chunks = len(base_chunks)
    async with httpx.AsyncClient(timeout=AGENTIC_CHUNK_TIMEOUT_SECONDS) as client:
        start = 0
        first_window = True
        while start < len(base_chunks):
            window_size = AGENTIC_CHUNK_WINDOW_SIZE if first_window else max(1, AGENTIC_CHUNK_WINDOW_SIZE - 1)
            window = base_chunks[start:start + window_size]
            result = await agentic_refine_chunk_window(
                client,
                carryover,
                window,
                interaction_log_path,
                relative_path,
            )
            if result is None:
                refined_chunks.extend(carryover + window)
                carryover = []
                first_window = False
                start += window_size
            else:
                refined_chunks.extend(result["final_chunks"])
                carryover = result["carryover"]
                if len(carryover) > 1:
                    carryover = ["\n\n".join(carryover).strip()]
                first_window = False
                start += window_size

            if on_progress is not None:
                await on_progress(min(1.0, start / total_base_chunks))

    refined_chunks.extend(carryover)
    return normalize_agentic_chunks([chunk for chunk in refined_chunks if chunk])


def normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


async def agentic_refine_chunk_window(
    client: httpx.AsyncClient,
    carryover: list[str],
    window: list[str],
    interaction_log_path: Path,
    relative_path: str,
) -> dict | None:
    prompt = build_agentic_chunk_prompt(carryover, window)
    response_text = ""
    error_message = None
    result = None
    try:
        response = await client.post(
            OLLAMA_CHUNK_URL,
            json={
                "model": AGENTIC_CHUNK_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_ctx": 8192,
                },
            },
        )
        response.raise_for_status()
        response_text = response.json().get("response", "")
        result = parse_agentic_chunk_response(response_text)
        return result
    except Exception as exc:
        error_message = str(exc)
        return None
    finally:
        await append_agentic_chunk_interaction(
            interaction_log_path,
            {
                "source": relative_path,
                "carryover_chunks": carryover,
                "window_chunks": window,
                "prompt": prompt,
                "reply": response_text,
                "parsed_result": {
                    "final_chunks": result["final_chunks"] if isinstance(result, dict) else None,
                    "carryover": result["carryover"] if isinstance(result, dict) else None,
                },
                "error": error_message,
            },
        )


def build_agentic_chunk_prompt(carryover: list[str], window: list[str]) -> str:
    carryover_text = format_numbered_chunks(carryover, "C")
    window_text = format_numbered_chunks(window, "N")
    return f"""You are refining confidential company knowledge-base chunks for retrieval.

You will receive:
- CARRYOVER chunks: text from the previous window that was not finalized because it may need to merge with upcoming context.
- NEW chunks: the next {len(window)} recursive character chunks.

The first request will receive 5 NEW chunks. Later requests will receive exactly 1 CARRYOVER chunk plus 4 NEW chunks.

Decide whether these chunks should stay separate, be combined, or be broken further.
Rules:
- Preserve the original wording exactly.
- Do not summarize, rewrite, redact, invent, or omit content.
- Keep related clauses, definitions, exceptions, and steps together.
- Prefer chunks around {AGENTIC_CHUNK_TARGET_CHARS} characters.
- Do not exceed {AGENTIC_CHUNK_MAX_CHARS} characters unless a single paragraph is longer.
- If text at the end may need the next window to form a complete semantic chunk, put it in "carryover".
- Return at most one carryover chunk. If the trailing text needs to wait for the next call, put the full trailing text into "carryover".
- "final_chunks" must contain only text that is complete enough to embed now.
- "carryover" must contain only trailing text that should wait for the next window.
- Return only valid JSON in this exact shape:
{{"final_chunks":["complete chunk"],"carryover":["trailing chunk that may continue"]}}

CARRYOVER chunks:
{carryover_text or "(none)"}

NEW chunks:
{window_text}"""


def format_numbered_chunks(chunks: list[str], prefix: str) -> str:
    return "\n\n".join(f"[{prefix}{index + 1}]\n{chunk}" for index, chunk in enumerate(chunks))


def agentic_chunk_log_path(knowledge_base_dir: Path) -> Path:
    path = knowledge_base_dir / VECTOR_STORE_NAME / AGENTIC_CHUNK_INTERACTION_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def append_agentic_chunk_interaction(log_path: Path, record: dict) -> None:
    record["timestamp"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_agentic_chunk_response(response_text: str) -> dict | None:
    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.strip("`")
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

    start = response_text.find("{")
    end = response_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        payload = json.loads(response_text[start:end + 1])
    except json.JSONDecodeError:
        return None

    final_chunks = payload.get("final_chunks", [])
    carryover = payload.get("carryover", [])
    if not isinstance(final_chunks, list) or not isinstance(carryover, list):
        return None

    return {
        "final_chunks": clean_chunk_list(final_chunks),
        "carryover": clean_chunk_list(carryover),
    }


def clean_chunk_list(chunks: list) -> list[str]:
    return [chunk.strip() for chunk in chunks if isinstance(chunk, str) and chunk.strip()]


def normalize_agentic_chunks(chunks: list[str]) -> list[str]:
    normalized = []
    for chunk in chunks:
        if len(chunk) <= AGENTIC_CHUNK_MAX_CHARS:
            normalized.append(chunk)
        else:
            normalized.extend(fallback_split_text(chunk, AGENTIC_CHUNK_MAX_CHARS, 0))
    return normalized


def fallback_split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not normalized:
        return []

    chunks = recursive_split(normalized, chunk_size, ["\n\n", "\n", ". ", " ", ""])
    merged = []
    current = ""

    for chunk in chunks:
        if not chunk:
            continue
        if not current:
            current = chunk
            continue
        candidate = f"{current}\n{chunk}"
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            merged.append(current.strip())
            overlap_text = current[-overlap:] if overlap > 0 else ""
            current = f"{overlap_text}\n{chunk}".strip()

    if current:
        merged.append(current.strip())

    return [chunk for chunk in merged if chunk]


def recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()]

    separator = separators[0]
    remaining = separators[1:]
    if separator == "":
        return [text[index:index + chunk_size].strip() for index in range(0, len(text), chunk_size)]

    pieces = text.split(separator)
    if len(pieces) == 1:
        return recursive_split(text, chunk_size, remaining)

    chunks = []
    current = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        candidate = piece if not current else f"{current}{separator}{piece}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.extend(recursive_split(current, chunk_size, remaining))
        current = piece

    if current:
        chunks.extend(recursive_split(current, chunk_size, remaining))
    return chunks

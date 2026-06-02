import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).with_name("history.db")


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                thread_context TEXT DEFAULT '',
                rag_context TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
            )
        """)
        ensure_message_context_columns(conn)
        migrate_old_logs(conn)


def ensure_message_context_columns(conn):
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(messages)").fetchall()
    }
    if "thread_context" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN thread_context TEXT DEFAULT ''")
    if "rag_context" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN rag_context TEXT DEFAULT ''")


def get_global_context() -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            ("global_context",),
        ).fetchone()
        return row["value"] if row else ""


def set_global_context(value: str):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            ("global_context", value.strip()),
        )


def migrate_old_logs(conn):
    old_logs_exists = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'logs'
    """).fetchone()
    if not old_logs_exists:
        return

    migrated = conn.execute("""
        SELECT 1 FROM threads
        WHERE title = 'Previous conversation'
        LIMIT 1
    """).fetchone()
    if migrated:
        return

    old_logs = conn.execute("""
        SELECT prompt, response, created_at
        FROM logs
        ORDER BY id ASC
    """).fetchall()
    if not old_logs:
        return

    thread_id = create_thread("Previous conversation", conn=conn)
    for row in old_logs:
        created_at = row["created_at"] if "created_at" in row.keys() else None
        add_message(thread_id, "user", row["prompt"], conn=conn, created_at=created_at)
        add_message(thread_id, "assistant", row["response"], conn=conn, created_at=created_at)


def create_thread(title: str = "New conversation", conn=None) -> int:
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO threads (title) VALUES (?)",
            (title.strip() or "New conversation",),
        )
        if owns_connection:
            conn.commit()
        return cursor.lastrowid
    finally:
        if owns_connection:
            conn.close()


def list_threads():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                threads.id,
                threads.title,
                threads.created_at,
                threads.updated_at,
                COUNT(messages.id) AS message_count
            FROM threads
            LEFT JOIN messages ON messages.thread_id = threads.id
            GROUP BY threads.id
            ORDER BY datetime(threads.updated_at) DESC, threads.id DESC
        """).fetchall()
        return [dict(row) for row in rows]


def get_thread(thread_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM threads WHERE id = ?",
            (thread_id,),
        ).fetchone()
        return dict(row) if row else None


def get_or_create_first_thread() -> int:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT id FROM threads
            ORDER BY datetime(updated_at) DESC, id DESC
            LIMIT 1
        """).fetchone()
        if row:
            return row["id"]
        return create_thread(conn=conn)


def add_message(
    thread_id: int,
    role: str,
    content: str,
    conn=None,
    created_at=None,
    thread_context: str = "",
    rag_context: str = "",
) -> int:
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        if created_at:
            cursor = conn.execute(
                """
                INSERT INTO messages (thread_id, role, content, thread_context, rag_context, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (thread_id, role, content, thread_context, rag_context, created_at),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO messages (thread_id, role, content, thread_context, rag_context)
                VALUES (?, ?, ?, ?, ?)
                """,
                (thread_id, role, content, thread_context, rag_context),
            )
        conn.execute(
            "UPDATE threads SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (thread_id,),
        )
        if owns_connection:
            conn.commit()
        return cursor.lastrowid
    finally:
        if owns_connection:
            conn.close()


def get_messages(thread_id: int):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, thread_id, role, content, thread_context, rag_context, created_at
            FROM messages
            WHERE thread_id = ?
            ORDER BY id ASC
        """, (thread_id,)).fetchall()
        return [dict(row) for row in rows]


def rename_thread(thread_id: int, title: str):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE threads
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title.strip() or "New conversation", thread_id),
        )


def title_from_prompt(prompt: str) -> str:
    words = prompt.strip().split()
    title = " ".join(words[:8])
    if len(title) > 60:
        title = title[:57].rstrip() + "..."
    return title or "New conversation"

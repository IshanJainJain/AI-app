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
        # ── Users ────────────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                email           TEXT    NOT NULL UNIQUE,
                username        TEXT    NOT NULL UNIQUE,
                hashed_password TEXT,
                google_id       TEXT    UNIQUE,
                created_at      TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── Settings ─────────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # ── Threads ───────────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title      TEXT    NOT NULL,
                created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── Messages ─────────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id  INTEGER NOT NULL,
                role       TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                content    TEXT    NOT NULL,
                created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
            )
        """)

        # ── Image contexts ────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS image_contexts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id   INTEGER NOT NULL,
                filename    TEXT    NOT NULL,
                description TEXT    NOT NULL,
                model       TEXT    NOT NULL,
                created_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
            )
        """)

        _run_migrations(conn)
        migrate_old_logs(conn)


def _run_migrations(conn):
    """Incremental ALTER TABLE migrations — safe to run on every startup."""

    # Add user_id to threads if upgrading from a pre-auth database
    thread_columns = {row[1] for row in conn.execute("PRAGMA table_info(threads)")}
    if "user_id" not in thread_columns:
        # Create a temporary system user to own all legacy threads
        conn.execute("""
            INSERT OR IGNORE INTO users (email, username)
            VALUES ('legacy@local', 'legacy')
        """)
        legacy_user = conn.execute(
            "SELECT id FROM users WHERE email = 'legacy@local'"
        ).fetchone()
        conn.execute("ALTER TABLE threads ADD COLUMN user_id INTEGER")
        conn.execute(
            "UPDATE threads SET user_id = ? WHERE user_id IS NULL",
            (legacy_user["id"],),
        )

    # Add thread_id to image_contexts if missing (your existing migration)
    image_columns = {row[1] for row in conn.execute("PRAGMA table_info(image_contexts)")}
    if "thread_id" not in image_columns:
        conn.execute("ALTER TABLE image_contexts ADD COLUMN thread_id INTEGER")
        default_thread = conn.execute("""
            SELECT id FROM threads
            ORDER BY datetime(updated_at) DESC, id DESC
            LIMIT 1
        """).fetchone()
        if default_thread:
            conn.execute(
                "UPDATE image_contexts SET thread_id = ? WHERE thread_id IS NULL",
                (default_thread["id"],),
            )

    # Migrate global_context key to per-user format handled at query time —
    # old 'global_context' key is left in place and ignored going forward.


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(email: str, username: str, hashed_password: str = None, google_id: str = None) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, username, hashed_password, google_id)
            VALUES (?, ?, ?, ?)
            """,
            (email.strip().lower(), username.strip(), hashed_password, google_id),
        )
        return cursor.lastrowid


def get_user_by_email(email: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_google_id(google_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE google_id = ?",
            (google_id,),
        ).fetchone()
        return dict(row) if row else None

def get_user_by_username(username: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        return dict(row) if row else None

def link_google_id(user_id: int, google_id: str):
    """Link a Google account to an existing email/password user."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET google_id = ? WHERE id = ?",
            (google_id, user_id),
        )


# ── Global context (per-user) ─────────────────────────────────────────────────

def _global_context_key(user_id: int) -> str:
    return f"global_context:{user_id}"


def get_global_context(user_id: int) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (_global_context_key(user_id),),
        ).fetchone()
        return row["value"] if row else ""


def set_global_context(user_id: int, value: str):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (_global_context_key(user_id), value.strip()),
        )


def delete_global_context(user_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM settings WHERE key = ?",
            (_global_context_key(user_id),),
        )


# ── Image contexts ────────────────────────────────────────────────────────────

def add_image_context(thread_id: int, filename: str, description: str, model: str):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO image_contexts (thread_id, filename, description, model)
            VALUES (?, ?, ?, ?)
            """,
            (thread_id, filename.strip() or "uploaded-image", description.strip(), model),
        )
        return cursor.lastrowid


def list_image_contexts(thread_id: int):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, thread_id, filename, description, model, created_at
            FROM image_contexts
            WHERE thread_id = ?
            ORDER BY id DESC
        """, (thread_id,)).fetchall()
        return [dict(row) for row in rows]


def delete_image_context(thread_id: int, image_context_id: int):
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM image_contexts WHERE id = ? AND thread_id = ?",
            (image_context_id, thread_id),
        )
        return cursor.rowcount > 0


# ── Threads ───────────────────────────────────────────────────────────────────

def create_thread(user_id: int, title: str = "New conversation", conn=None) -> int:
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO threads (user_id, title) VALUES (?, ?)",
            (user_id, title.strip() or "New conversation"),
        )
        if owns_connection:
            conn.commit()
        return cursor.lastrowid
    finally:
        if owns_connection:
            conn.close()


def list_threads(user_id: int):
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
            WHERE threads.user_id = ?
            GROUP BY threads.id
            ORDER BY datetime(threads.updated_at) DESC, threads.id DESC
        """, (user_id,)).fetchall()
        return [dict(row) for row in rows]


def get_thread(thread_id: int, user_id: int):
    """Returns thread only if it belongs to user_id — prevents cross-user access."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM threads WHERE id = ? AND user_id = ?",
            (thread_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def delete_thread(thread_id: int, user_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM image_contexts WHERE thread_id = ?", (thread_id,))
        cursor = conn.execute(
            "DELETE FROM threads WHERE id = ? AND user_id = ?",
            (thread_id, user_id),
        )
        return cursor.rowcount > 0


def get_or_create_first_thread(user_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT id FROM threads
            WHERE user_id = ?
            ORDER BY datetime(updated_at) DESC, id DESC
            LIMIT 1
        """, (user_id,)).fetchone()
        if row:
            return row["id"]
        return create_thread(user_id=user_id, conn=conn)


def rename_thread(thread_id: int, user_id: int, title: str):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE threads
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (title.strip() or "New conversation", thread_id, user_id),
        )


# ── Messages ──────────────────────────────────────────────────────────────────

def add_message(thread_id: int, role: str, content: str, conn=None, created_at=None) -> int:
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        if created_at:
            cursor = conn.execute(
                "INSERT INTO messages (thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (thread_id, role, content, created_at),
            )
        else:
            cursor = conn.execute(
                "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
                (thread_id, role, content),
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
            SELECT id, thread_id, role, content, created_at
            FROM messages
            WHERE thread_id = ?
            ORDER BY id ASC
        """, (thread_id,)).fetchall()
        return [dict(row) for row in rows]


# ── Helpers ───────────────────────────────────────────────────────────────────

def title_from_prompt(prompt: str) -> str:
    words = prompt.strip().split()
    title = " ".join(words[:8])
    if len(title) > 60:
        title = title[:57].rstrip() + "..."
    return title or "New conversation"


def migrate_old_logs(conn):
    """One-time migration from the legacy 'logs' table."""
    old_logs_exists = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'logs'
    """).fetchone()
    if not old_logs_exists:
        return

    migrated = conn.execute("""
        SELECT 1 FROM threads WHERE title = 'Previous conversation' LIMIT 1
    """).fetchone()
    if migrated:
        return

    old_logs = conn.execute("""
        SELECT prompt, response, created_at FROM logs ORDER BY id ASC
    """).fetchall()
    if not old_logs:
        return

    # Assign legacy logs to the legacy user created during migration
    legacy_user = conn.execute(
        "SELECT id FROM users WHERE email = 'legacy@local'"
    ).fetchone()
    if not legacy_user:
        return

    thread_id = create_thread(user_id=legacy_user["id"], title="Previous conversation", conn=conn)
    for row in old_logs:
        created_at = row["created_at"] if "created_at" in row.keys() else None
        add_message(thread_id, "user", row["prompt"], conn=conn, created_at=created_at)
        add_message(thread_id, "assistant", row["response"], conn=conn, created_at=created_at)
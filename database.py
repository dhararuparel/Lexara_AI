"""
PostgreSQL database layer — Lexara AI
Uses psycopg2 with connection pooling for fast repeated queries.
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from dotenv import load_dotenv
import base64
from cryptography.fernet import Fernet

def get_encryption_key() -> bytes:
    key = os.getenv("DB_ENCRYPTION_KEY")
    if key:
        return key.encode()
    secret = os.getenv("SECRET_KEY", "Lexara-default-fallback-key-for-encryption-rest")
    import hashlib
    h = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(h)

_cipher = None
def get_cipher():
    global _cipher
    if _cipher is None:
        _cipher = Fernet(get_encryption_key())
    return _cipher

def encrypt_value(val: str) -> str:
    if not val:
        return val
    try:
        cipher = get_cipher()
        return cipher.encrypt(val.encode()).decode()
    except Exception:
        return val

def decrypt_value(val: str) -> str:
    if not val:
        return val
    try:
        cipher = get_cipher()
        return cipher.decrypt(val.encode()).decode()
    except Exception:
        return val

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Connection pool — reuses connections instead of opening a new one per request
_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            dsn=DATABASE_URL,
            connect_timeout=10,
        )
    return _pool

def get_conn():
    return _get_pool().getconn()

def release_conn(conn):
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass

from contextlib import contextmanager

@contextmanager
def _conn():
    """Context manager that borrows a connection from the pool and returns it after use."""
    conn = _get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


def _row(cursor, one=True):
    """Fetch one or all rows as plain dicts, with datetime serialized to ISO strings."""
    import datetime
    cols = [d[0] for d in cursor.description]
    def _serialize(k, v):
        if isinstance(v, (datetime.datetime, datetime.date)):
            return v.isoformat()
        if k in {"totp_secret", "text", "parent_text", "secret"} and isinstance(v, str):
            return decrypt_value(v)
        return v
    if one:
        row = cursor.fetchone()
        return {k: _serialize(k, v) for k, v in zip(cols, row)} if row else None
    return [{k: _serialize(k, v) for k, v in zip(cols, row)} for row in cursor.fetchall()]


def init_db():
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         SERIAL PRIMARY KEY,
                name       TEXT NOT NULL,
                email      TEXT UNIQUE NOT NULL,
                password   TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS folders (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                color      TEXT DEFAULT '#8b5cf6',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS documents (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                folder_id  INTEGER REFERENCES folders(id) ON DELETE SET NULL,
                filename   TEXT NOT NULL,
                orig_name  TEXT NOT NULL,
                file_size  BIGINT DEFAULT 0,
                file_type  TEXT DEFAULT 'pdf',
                pages      INTEGER DEFAULT 0,
                chunks     INTEGER DEFAULT 0,
                version    INTEGER DEFAULT 1,
                parent_id  INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                full_text  TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS chunk_store (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                doc_name   TEXT NOT NULL,
                page_num   INTEGER DEFAULT 1,
                chunk_idx  INTEGER DEFAULT 0,
                text       TEXT NOT NULL,
                parent_text TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS chats (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title      TEXT DEFAULT 'New Chat',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS messages (
                id           SERIAL PRIMARY KEY,
                chat_id      INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role         TEXT NOT NULL,
                content      TEXT NOT NULL,
                sources      TEXT DEFAULT NULL,
                confidence   REAL DEFAULT NULL,
                followups    TEXT DEFAULT NULL,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS message_feedback (
                id         SERIAL PRIMARY KEY,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                rating     SMALLINT NOT NULL CHECK (rating IN (1, -1)),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS pinned_messages (
                id         SERIAL PRIMARY KEY,
                chat_id    INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS document_tags (
                id         SERIAL PRIMARY KEY,
                doc_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tag        TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS team_members (
                id           SERIAL PRIMARY KEY,
                owner_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                member_email TEXT NOT NULL,
                role         TEXT NOT NULL DEFAULT 'viewer'
                               CHECK (role IN ('admin','editor','viewer')),
                status       TEXT NOT NULL DEFAULT 'pending'
                               CHECK (status IN ('pending','active')),
                created_at   TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS saved_prompts (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title      TEXT NOT NULL,
                prompt     TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS collections (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                color       TEXT DEFAULT '#8b5cf6',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS collection_documents (
                collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                doc_id        INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                PRIMARY KEY (collection_id, doc_id)
            );
            ALTER TABLE documents ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ DEFAULT NULL;
            ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash  TEXT DEFAULT '';
            ALTER TABLE users     ADD COLUMN IF NOT EXISTS email_verified   BOOLEAN DEFAULT FALSE;
            ALTER TABLE users     ADD COLUMN IF NOT EXISTS verify_token     TEXT DEFAULT NULL;
            ALTER TABLE users     ADD COLUMN IF NOT EXISTS reset_token      TEXT DEFAULT NULL;
            ALTER TABLE users     ADD COLUMN IF NOT EXISTS reset_expires    TIMESTAMPTZ DEFAULT NULL;
            ALTER TABLE users     ADD COLUMN IF NOT EXISTS totp_secret      TEXT DEFAULT NULL;
            ALTER TABLE users     ADD COLUMN IF NOT EXISTS totp_enabled     BOOLEAN DEFAULT FALSE;
            CREATE TABLE IF NOT EXISTS user_sessions (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash  TEXT UNIQUE NOT NULL,
                device_info TEXT DEFAULT '',
                ip_address  TEXT DEFAULT '',
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                last_seen   TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS chat_shares (
                id         SERIAL PRIMARY KEY,
                chat_id    INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token      TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS chat_branches (
                id            SERIAL PRIMARY KEY,
                parent_chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                branch_chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                branch_msg_id  INTEGER REFERENCES messages(id) ON DELETE SET NULL,
                created_at     TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS workspaces (
                id          SERIAL PRIMARY KEY,
                owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS workspace_members (
                id           SERIAL PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
                email        TEXT NOT NULL,
                role         TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin','editor','viewer')),
                status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active')),
                invited_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
                invite_token TEXT DEFAULT NULL,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS workspace_documents (
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                doc_id       INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                added_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                added_at     TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (workspace_id, doc_id)
            );
            CREATE TABLE IF NOT EXISTS message_comments (
                id         SERIAL PRIMARY KEY,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content    TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                action      TEXT NOT NULL,
                target_type TEXT DEFAULT '',
                target_id   INTEGER DEFAULT NULL,
                target_name TEXT DEFAULT '',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            ALTER TABLE users ADD COLUMN IF NOT EXISTS tier        TEXT DEFAULT 'free' CHECK (tier IN ('free','pro','enterprise'));
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin    BOOLEAN DEFAULT FALSE;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_ref TEXT DEFAULT NULL;
            ALTER TABLE workspace_members ADD COLUMN IF NOT EXISTS invite_token TEXT DEFAULT NULL;
            CREATE TABLE IF NOT EXISTS api_keys (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                key_hash    TEXT UNIQUE NOT NULL,
                key_prefix  TEXT NOT NULL,
                label       TEXT DEFAULT 'Default',
                last_used   TIMESTAMPTZ DEFAULT NULL,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS white_label (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
                app_name    TEXT DEFAULT 'Lexara AI',
                logo_url    TEXT DEFAULT '',
                primary_color TEXT DEFAULT '#8b5cf6',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS webhooks (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                url         TEXT NOT NULL,
                events      TEXT NOT NULL DEFAULT 'document_uploaded,query_made',
                secret      TEXT DEFAULT '',
                active      BOOLEAN DEFAULT TRUE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS auth_failures (
                key TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                last_failed_at TIMESTAMPTZ DEFAULT NOW(),
                lockout_until TIMESTAMPTZ
            );
            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT PRIMARY KEY,
                requests INTEGER DEFAULT 0,
                window_start TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS token_blocklist (
                token_hash VARCHAR(64) PRIMARY KEY,
                blacklisted_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ
            );
            """)
        conn.commit()


# ── Users ──────────────────────────────────────────────────────────

def create_user(name, email, hashed_password):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (name, email, password) VALUES (%s,%s,%s) RETURNING *",
                (name, email, hashed_password)
            )
            row = _row(cur)
        conn.commit()
    return row


def get_user_by_email(email):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            return _row(cur)


def get_user_by_id(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            return _row(cur)


# ── Documents ──────────────────────────────────────────────────────

def add_document(user_id, filename, orig_name, file_size, file_type, pages, chunks,
                  folder_id=None, full_text='', parent_id=None, version=1):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO documents
                   (user_id,folder_id,filename,orig_name,file_size,file_type,pages,chunks,full_text,parent_id,version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (user_id, folder_id, filename, orig_name, file_size, file_type,
                 pages, chunks, full_text, parent_id, version)
            )
            row = _row(cur)
        conn.commit()
    return row


def get_user_documents(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM documents WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,)
            )
            return _row(cur, one=False)


def delete_document(doc_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM documents WHERE id=%s AND user_id=%s",
                (doc_id, user_id)
            )
            row = _row(cur)
            if not row:
                return None
            cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
        conn.commit()
    return row


def get_document_stats(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) AS docs,
                          COALESCE(SUM(chunks),0) AS chunks,
                          COALESCE(SUM(pages),0)  AS pages
                   FROM documents WHERE user_id=%s""",
                (user_id,)
            )
            return _row(cur)


# ── Chats ──────────────────────────────────────────────────────────

def create_chat(user_id, title="New Chat"):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chats (user_id, title) VALUES (%s,%s) RETURNING *",
                (user_id, title)
            )
            row = _row(cur)
        conn.commit()
    return row


def get_user_chats(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM chats WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,)
            )
            return _row(cur, one=False)


def update_chat_title(chat_id, title):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE chats SET title=%s WHERE id=%s", (title, chat_id))
        conn.commit()


def delete_chat(chat_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM messages WHERE chat_id=%s", (chat_id,))
            cur.execute("DELETE FROM chats WHERE id=%s AND user_id=%s", (chat_id, user_id))
        conn.commit()


# ── Messages ───────────────────────────────────────────────────────

def add_message(chat_id, role, content, sources=None, confidence=None, followups=None):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (chat_id, role, content, sources, confidence, followups) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (chat_id, role, content, sources, confidence, followups)
            )
            row = cur.fetchone()
        conn.commit()
    return row[0] if row else None


def get_chat_messages(chat_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM messages WHERE chat_id=%s ORDER BY created_at ASC",
                (chat_id,)
            )
            return _row(cur, one=False)


# ── Analytics ──────────────────────────────────────────────────────

def get_analytics(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents WHERE user_id=%s", (user_id,))
            docs = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(chunks),0) FROM documents WHERE user_id=%s", (user_id,))
            chunks = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chats WHERE user_id=%s", (user_id,))
            chats = cur.fetchone()[0]
            cur.execute(
                """SELECT COUNT(*) FROM messages m
                   JOIN chats c ON m.chat_id=c.id
                   WHERE c.user_id=%s AND m.role='user'""",
                (user_id,)
            )
            queries = cur.fetchone()[0]
    return {"docs": docs, "chunks": chunks, "chats": chats, "queries": queries}


# ── Message Feedback ───────────────────────────────────────────────

def add_feedback(message_id, rating):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO message_feedback (message_id, rating) VALUES (%s,%s)",
                (message_id, rating)
            )
        conn.commit()


# ── Pinned Messages ────────────────────────────────────────────────

def get_pinned(chat_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT pm.id AS pin_id, m.id, m.role, m.content, m.sources, m.created_at
                   FROM pinned_messages pm
                   JOIN messages m ON pm.message_id=m.id
                   WHERE pm.chat_id=%s ORDER BY pm.created_at ASC""",
                (chat_id,)
            )
            return _row(cur, one=False)


def pin_message(chat_id, message_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM pinned_messages WHERE chat_id=%s AND message_id=%s",
                (chat_id, message_id)
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO pinned_messages (chat_id, message_id) VALUES (%s,%s)",
                    (chat_id, message_id)
                )
        conn.commit()


def unpin_message(message_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pinned_messages WHERE message_id=%s", (message_id,))
        conn.commit()


# ── Document Tags ──────────────────────────────────────────────────

def add_tag(doc_id, user_id, tag):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO document_tags (doc_id, user_id, tag) VALUES (%s,%s,%s) RETURNING *",
                (doc_id, user_id, tag)
            )
            row = _row(cur)
        conn.commit()
    return row


def remove_tag(tag_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_tags WHERE id=%s", (tag_id,))
        conn.commit()


def get_doc_tags(doc_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM document_tags WHERE doc_id=%s ORDER BY created_at ASC",
                (doc_id,)
            )
            return _row(cur, one=False)


# ── Team Members ───────────────────────────────────────────────────

def invite_member(owner_id, email, role="viewer"):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO team_members (owner_id, member_email, role, status)
                   VALUES (%s,%s,%s,'pending') RETURNING *""",
                (owner_id, email, role)
            )
            row = _row(cur)
        conn.commit()
    return row


def get_team(owner_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM team_members WHERE owner_id=%s ORDER BY created_at ASC",
                (owner_id,)
            )
            return _row(cur, one=False)


def update_member_role(member_id, role):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE team_members SET role=%s WHERE id=%s", (role, member_id))
        conn.commit()


def remove_member(member_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM team_members WHERE id=%s", (member_id,))
        conn.commit()


# ── Message Search ─────────────────────────────────────────────────

def search_messages(user_id, query):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id, m.chat_id, m.role, m.content, m.created_at, c.title AS chat_title
                   FROM messages m
                   JOIN chats c ON m.chat_id=c.id
                   WHERE c.user_id=%s AND m.content ILIKE %s
                   ORDER BY m.created_at DESC LIMIT 50""",
                (user_id, f"%{query}%")
            )
            return _row(cur, one=False)


# ── Folders ────────────────────────────────────────────────────────

def create_folder(user_id, name, color='#8b5cf6'):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO folders (user_id, name, color) VALUES (%s,%s,%s) RETURNING *",
                (user_id, name, color)
            )
            row = _row(cur)
        conn.commit()
    return row


def get_user_folders(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM folders WHERE user_id=%s ORDER BY created_at ASC",
                (user_id,)
            )
            return _row(cur, one=False)


def delete_folder(folder_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            # Unassign docs from folder before deleting
            cur.execute("UPDATE documents SET folder_id=NULL WHERE folder_id=%s AND user_id=%s",
                        (folder_id, user_id))
            cur.execute("DELETE FROM folders WHERE id=%s AND user_id=%s", (folder_id, user_id))
        conn.commit()


def move_document_to_folder(doc_id, user_id, folder_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET folder_id=%s WHERE id=%s AND user_id=%s",
                (folder_id, doc_id, user_id)
            )
        conn.commit()


# ── Document versioning ────────────────────────────────────────────

def get_document_versions(orig_name, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM documents WHERE user_id=%s AND orig_name=%s
                   ORDER BY version DESC""",
                (user_id, orig_name)
            )
            return _row(cur, one=False)


def get_latest_version(orig_name, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(version),0) FROM documents WHERE user_id=%s AND orig_name=%s",
                (user_id, orig_name)
            )
            row = cur.fetchone()
            return row[0] if row else 0


# ── Full-text search across document content ───────────────────────

def search_document_content(user_id, query):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, orig_name, file_type, pages,
                          ts_headline('english', full_text, plainto_tsquery('english',%s),
                                      'MaxWords=20, MinWords=10') AS snippet
                   FROM documents
                   WHERE user_id=%s
                     AND full_text != ''
                     AND to_tsvector('english', full_text) @@ plainto_tsquery('english', %s)
                   ORDER BY ts_rank(to_tsvector('english', full_text),
                                    plainto_tsquery('english', %s)) DESC
                   LIMIT 20""",
                (query, user_id, query, query)
            )
            return _row(cur, one=False)


# ── Chunk Store (persistent backup of all embeddings text) ─────────

def save_chunks(user_id, chunks):
    """Persist chunk texts to DB so vector store can be rebuilt on restart."""
    if not chunks:
        return
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO chunk_store
                   (user_id, doc_name, page_num, chunk_idx, text, parent_text)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                [(user_id,
                  c.get("source",""),
                  c.get("page", 1),
                  c.get("chunk_index", 0),
                  encrypt_value(c.get("text","")),
                  encrypt_value(c.get("parent_text","")))
                 for c in chunks]
            )
        conn.commit()


def load_chunks(user_id):
    """Load all chunk texts for a user from DB."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT doc_name, page_num, chunk_idx, text, parent_text
                   FROM chunk_store WHERE user_id=%s
                   ORDER BY doc_name, chunk_idx""",
                (user_id,)
            )
            rows = cur.fetchall()
    return [{"source": r[0], "page": r[1], "chunk_index": r[2],
             "text": r[3], "parent_text": r[4]} for r in rows]


def delete_chunks(user_id, doc_name=None):
    """Delete chunks for a user, optionally filtered by document name."""
    with _conn() as conn:
        with conn.cursor() as cur:
            if doc_name:
                cur.execute(
                    "DELETE FROM chunk_store WHERE user_id=%s AND doc_name=%s",
                    (user_id, doc_name)
                )
            else:
                cur.execute("DELETE FROM chunk_store WHERE user_id=%s", (user_id,))
        conn.commit()


# ── Saved Prompts ──────────────────────────────────────────────────

def get_saved_prompts(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM saved_prompts WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,)
            )
            return _row(cur, one=False)


def create_saved_prompt(user_id, title, prompt):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO saved_prompts (user_id, title, prompt) VALUES (%s,%s,%s) RETURNING *",
                (user_id, title, prompt)
            )
            row = _row(cur)
        conn.commit()
    return row


def delete_saved_prompt(prompt_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM saved_prompts WHERE id=%s AND user_id=%s",
                (prompt_id, user_id)
            )
        conn.commit()


# ── Chat Sharing ───────────────────────────────────────────────────

def create_share_token(chat_id, user_id):
    import secrets
    token = secrets.token_urlsafe(24)
    with _conn() as conn:
        with conn.cursor() as cur:
            # Remove existing share for this chat
            cur.execute("DELETE FROM chat_shares WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
            cur.execute(
                "INSERT INTO chat_shares (chat_id, user_id, token) VALUES (%s,%s,%s) RETURNING *",
                (chat_id, user_id, token)
            )
            row = _row(cur)
        conn.commit()
    return row


def get_share_by_token(token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT cs.*, c.title, c.user_id
                   FROM chat_shares cs JOIN chats c ON cs.chat_id=c.id
                   WHERE cs.token=%s""",
                (token,)
            )
            return _row(cur)


def get_share_by_chat(chat_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM chat_shares WHERE chat_id=%s AND user_id=%s",
                (chat_id, user_id)
            )
            return _row(cur)


# ── Chat Branching ─────────────────────────────────────────────────

def create_branch(parent_chat_id, branch_chat_id, branch_msg_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO chat_branches (parent_chat_id, branch_chat_id, branch_msg_id)
                   VALUES (%s,%s,%s) RETURNING *""",
                (parent_chat_id, branch_chat_id, branch_msg_id)
            )
            row = _row(cur)
        conn.commit()
    return row


def get_branches(parent_chat_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT cb.*, c.title
                   FROM chat_branches cb JOIN chats c ON cb.branch_chat_id=c.id
                   WHERE cb.parent_chat_id=%s ORDER BY cb.created_at DESC""",
                (parent_chat_id,)
            )
            return _row(cur, one=False)


# ── Saved Prompts ──────────────────────────────────────────────────

def get_saved_prompts(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM saved_prompts WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
            return _row(cur, one=False)

def create_saved_prompt(user_id, title, prompt):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO saved_prompts (user_id,title,prompt) VALUES (%s,%s,%s) RETURNING *",
                        (user_id, title, prompt))
            row = _row(cur)
        conn.commit()
    return row

def delete_saved_prompt(prompt_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM saved_prompts WHERE id=%s AND user_id=%s", (prompt_id, user_id))
        conn.commit()

# ── Shared Chats ───────────────────────────────────────────────────

def create_share_token(chat_id, user_id):
    import secrets
    token = secrets.token_urlsafe(20)
    with _conn() as conn:
        with conn.cursor() as cur:
            # Remove existing share for this chat
            cur.execute("DELETE FROM chat_shares WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
            cur.execute("INSERT INTO chat_shares (chat_id,user_id,token) VALUES (%s,%s,%s) RETURNING *",
                        (chat_id, user_id, token))
            row = _row(cur)
        conn.commit()
    return row

def get_shared_chat(token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM chat_shares WHERE token=%s", (token,))
            return _row(cur)

def get_messages_by_chat(chat_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM messages WHERE chat_id=%s ORDER BY created_at ASC", (chat_id,))
            return _row(cur, one=False)

# ── Chat Branching ─────────────────────────────────────────────────

def create_branch(parent_chat_id, branch_chat_id, from_message_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_branches (parent_chat_id,branch_chat_id,from_message_id) VALUES (%s,%s,%s)",
                (parent_chat_id, branch_chat_id, from_message_id)
            )
        conn.commit()

def get_message_by_id(msg_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM messages WHERE id=%s", (msg_id,))
            return _row(cur)


# ── Collections ────────────────────────────────────────────────────

def get_user_collections(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM collections WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
            return _row(cur, one=False)

def create_collection(user_id, name, description='', color='#8b5cf6'):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO collections (user_id,name,description,color) VALUES (%s,%s,%s,%s) RETURNING *",
                        (user_id, name, description, color))
            row = _row(cur)
        conn.commit()
    return row

def delete_collection(col_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM collections WHERE id=%s AND user_id=%s", (col_id, user_id))
        conn.commit()

def add_doc_to_collection(col_id, doc_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO collection_documents (collection_id,doc_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (col_id, doc_id))
        conn.commit()

def remove_doc_from_collection(col_id, doc_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM collection_documents WHERE collection_id=%s AND doc_id=%s", (col_id, doc_id))
        conn.commit()

def get_collection_docs(col_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT d.* FROM documents d
                           JOIN collection_documents cd ON d.id=cd.doc_id
                           WHERE cd.collection_id=%s ORDER BY d.created_at DESC""", (col_id,))
            return _row(cur, one=False)

# ── Document expiry ────────────────────────────────────────────────

def set_doc_expiry(doc_id, user_id, expires_at):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE documents SET expires_at=%s WHERE id=%s AND user_id=%s",
                        (expires_at, doc_id, user_id))
        conn.commit()

def get_expired_documents():
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM documents WHERE expires_at IS NOT NULL AND expires_at < NOW()")
            return _row(cur, one=False)

# ── Duplicate detection ────────────────────────────────────────────

def get_doc_by_hash(user_id, file_hash):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM documents WHERE user_id=%s AND file_hash=%s LIMIT 1",
                        (user_id, file_hash))
            return _row(cur)

def set_doc_hash(doc_id, file_hash):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE documents SET file_hash=%s WHERE id=%s", (file_hash, doc_id))
        conn.commit()

# ── Sessions ───────────────────────────────────────────────────────

def create_session(user_id, token, device_info='', ip_address=''):
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO user_sessions (user_id,token_hash,device_info,ip_address)
                           VALUES (%s,%s,%s,%s) RETURNING *""",
                        (user_id, token_hash, device_info, ip_address))
            row = _row(cur)
        conn.commit()
    return row

def get_user_sessions(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM user_sessions WHERE user_id=%s ORDER BY last_seen DESC", (user_id,))
            return _row(cur, one=False)

def revoke_session(session_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_sessions WHERE id=%s AND user_id=%s", (session_id, user_id))
        conn.commit()

def revoke_all_sessions(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_sessions WHERE user_id=%s", (user_id,))
        conn.commit()

def touch_session(token):
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_sessions SET last_seen=NOW() WHERE token_hash=%s", (token_hash,))
        conn.commit()

# ── 2FA (TOTP) ─────────────────────────────────────────────────────

def set_totp_secret(user_id, secret):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET totp_secret=%s, totp_enabled=TRUE WHERE id=%s", (encrypt_value(secret), user_id))
        conn.commit()

def disable_totp(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET totp_secret=NULL, totp_enabled=FALSE WHERE id=%s", (user_id,))
        conn.commit()

# ── Email verification & password reset ───────────────────────────

def set_verify_token(user_id, token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET verify_token=%s WHERE id=%s", (token, user_id))
        conn.commit()

def verify_email(token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET email_verified=TRUE, verify_token=NULL WHERE verify_token=%s RETURNING id",
                        (token,))
            row = cur.fetchone()
        conn.commit()
    return row[0] if row else None

def set_reset_token(email, token, expires):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET reset_token=%s, reset_expires=%s WHERE email=%s",
                        (token, expires, email))
        conn.commit()

def get_user_by_reset_token(token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE reset_token=%s AND reset_expires > NOW()", (token,))
            return _row(cur)

def complete_password_reset(token, new_password):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password=%s, reset_token=NULL, reset_expires=NULL WHERE reset_token=%s",
                        (new_password, token))
        conn.commit()


# ── Sessions ───────────────────────────────────────────────────────

def create_session(user_id, token_hash, device_info='', ip_address=''):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_sessions (user_id, token_hash, device_info, ip_address)
                   VALUES (%s,%s,%s,%s) RETURNING *""",
                (user_id, token_hash, device_info, ip_address)
            )
            row = _row(cur)
        conn.commit()
    return row

def get_user_sessions(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM user_sessions WHERE user_id=%s ORDER BY last_seen DESC",
                (user_id,)
            )
            return _row(cur, one=False)

def revoke_session(session_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_sessions WHERE id=%s AND user_id=%s", (session_id, user_id))
        conn.commit()

def revoke_all_sessions(user_id, except_hash=None):
    with _conn() as conn:
        with conn.cursor() as cur:
            if except_hash:
                cur.execute("DELETE FROM user_sessions WHERE user_id=%s AND token_hash!=%s", (user_id, except_hash))
            else:
                cur.execute("DELETE FROM user_sessions WHERE user_id=%s", (user_id,))
        conn.commit()

def touch_session(token_hash):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_sessions SET last_seen=NOW() WHERE token_hash=%s", (token_hash,))
        conn.commit()

def session_exists(token_hash):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM user_sessions WHERE token_hash=%s", (token_hash,))
            return cur.fetchone() is not None

# ── Email verification & password reset ───────────────────────────

def set_verify_token(user_id, token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET verify_token=%s WHERE id=%s", (token, user_id))
        conn.commit()

def verify_email(token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE verify_token=%s", (token,))
            user = _row(cur)
            if user:
                cur.execute("UPDATE users SET email_verified=TRUE, verify_token=NULL WHERE id=%s", (user['id'],))
        conn.commit()
    return user

def set_reset_token(email, token, expires):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET reset_token=%s, reset_expires=%s WHERE email=%s",
                (token, expires, email)
            )
        conn.commit()

def get_user_by_reset_token(token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE reset_token=%s AND reset_expires > NOW()",
                (token,)
            )
            return _row(cur)

def clear_reset_token(user_id, new_password):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password=%s, reset_token=NULL, reset_expires=NULL WHERE id=%s",
                (new_password, user_id)
            )
        conn.commit()

# ── 2FA / TOTP ─────────────────────────────────────────────────────

def set_totp_secret(user_id, secret):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET totp_secret=%s, totp_enabled=FALSE WHERE id=%s", (encrypt_value(secret), user_id))
        conn.commit()

def enable_totp(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET totp_enabled=TRUE WHERE id=%s", (user_id,))
        conn.commit()

def disable_totp(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET totp_secret=NULL, totp_enabled=FALSE WHERE id=%s", (user_id,))
        conn.commit()

# ── Workspaces ─────────────────────────────────────────────────────

def create_workspace(owner_id, name, description=''):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workspaces (owner_id,name,description) VALUES (%s,%s,%s) RETURNING *",
                (owner_id, name, description)
            )
            row = _row(cur)
        conn.commit()
    return row

def get_user_workspaces(user_id):
    """Return workspaces owned by or member of."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT w.*, u.name AS owner_name,
                    COALESCE(wm.role, 'owner') AS my_role
                FROM workspaces w
                JOIN users u ON u.id = w.owner_id
                LEFT JOIN workspace_members wm ON wm.workspace_id=w.id AND wm.user_id=%s AND wm.status='active'
                WHERE w.owner_id=%s OR (wm.user_id=%s AND wm.status='active')
                ORDER BY w.created_at DESC
            """, (user_id, user_id, user_id))
            return _row(cur, one=False)

def get_workspace(workspace_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT w.*, u.name AS owner_name FROM workspaces w JOIN users u ON u.id=w.owner_id WHERE w.id=%s", (workspace_id,))
            return _row(cur)

def delete_workspace(workspace_id, owner_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM workspaces WHERE id=%s AND owner_id=%s", (workspace_id, owner_id))
        conn.commit()

def get_workspace_members(workspace_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT wm.*, u.name AS user_name
                FROM workspace_members wm
                LEFT JOIN users u ON u.id=wm.user_id
                WHERE wm.workspace_id=%s ORDER BY wm.created_at ASC
            """, (workspace_id,))
            return _row(cur, one=False)

def invite_workspace_member(workspace_id, email, role, invited_by):
    import secrets
    with _conn() as conn:
        with conn.cursor() as cur:
            # If already an active member, block
            cur.execute(
                "SELECT id, status FROM workspace_members WHERE workspace_id=%s AND email=%s",
                (workspace_id, email)
            )
            existing = cur.fetchone()
            if existing:
                status_val = existing[1]
                if status_val == 'active':
                    return None  # already a full member
                # Pending — replace with a fresh token (re-invite)
                cur.execute(
                    "DELETE FROM workspace_members WHERE workspace_id=%s AND email=%s",
                    (workspace_id, email)
                )
            # Check if user account exists
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            user_row = cur.fetchone()
            user_id = user_row[0] if user_row else None
            invite_token = secrets.token_urlsafe(32)
            cur.execute("""
                INSERT INTO workspace_members (workspace_id,user_id,email,role,status,invited_by,invite_token)
                VALUES (%s,%s,%s,%s,'pending',%s,%s) RETURNING *
            """, (workspace_id, user_id, email, role, invited_by, invite_token))
            row = _row(cur)
        conn.commit()
    return row


def get_workspace_invite_by_token(token):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT wm.*, w.name AS workspace_name, u.name AS inviter_name
                FROM workspace_members wm
                JOIN workspaces w ON w.id = wm.workspace_id
                LEFT JOIN users u ON u.id = wm.invited_by
                WHERE wm.invite_token=%s
            """, (token,))
            return _row(cur)


def accept_workspace_invite(token, user_id, email):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE workspace_members
                SET status='active', user_id=%s, invite_token=NULL
                WHERE invite_token=%s AND email=%s
                RETURNING *
            """, (user_id, token, email))
            row = _row(cur)
        conn.commit()
    return row

def remove_workspace_member(workspace_id, member_id, requester_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            # owner or admin can remove
            cur.execute("SELECT id FROM workspaces WHERE id=%s AND owner_id=%s", (workspace_id, requester_id))
            is_owner = cur.fetchone() is not None
            if not is_owner:
                cur.execute(
                    "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s AND status='active'",
                    (workspace_id, requester_id)
                )
                row = cur.fetchone()
                if not row or row[0] not in ('admin',):
                    return False
            # Prevent removing the owner themselves
            cur.execute("SELECT user_id FROM workspace_members WHERE id=%s AND workspace_id=%s", (member_id, workspace_id))
            target = cur.fetchone()
            if target:
                cur.execute("SELECT id FROM workspaces WHERE id=%s AND owner_id=%s", (workspace_id, target[0]))
                if cur.fetchone():
                    return False  # can't remove the owner
            cur.execute("DELETE FROM workspace_members WHERE id=%s AND workspace_id=%s", (member_id, workspace_id))
        conn.commit()
    return True

def update_member_role(workspace_id, member_id, role, requester_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM workspaces WHERE id=%s AND owner_id=%s", (workspace_id, requester_id))
            is_owner = cur.fetchone() is not None
            if not is_owner:
                cur.execute(
                    "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s AND status='active'",
                    (workspace_id, requester_id)
                )
                row = cur.fetchone()
                if not row or row[0] != 'admin':
                    return False
            cur.execute(
                "UPDATE workspace_members SET role=%s WHERE id=%s AND workspace_id=%s",
                (role, member_id, workspace_id)
            )
        conn.commit()
    return True

def update_workspace(workspace_id, requester_id, name, description):
    with _conn() as conn:
        with conn.cursor() as cur:
            # owner or admin can edit
            cur.execute("SELECT id FROM workspaces WHERE id=%s AND owner_id=%s", (workspace_id, requester_id))
            is_owner = cur.fetchone() is not None
            if not is_owner:
                cur.execute(
                    "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s AND status='active'",
                    (workspace_id, requester_id)
                )
                row = cur.fetchone()
                if not row or row[0] not in ('admin', 'editor'):
                    return False
            cur.execute(
                "UPDATE workspaces SET name=%s, description=%s WHERE id=%s RETURNING *",
                (name, description, workspace_id)
            )
            row = _row(cur)
        conn.commit()
    return row

def can_access_workspace(workspace_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM workspaces WHERE id=%s AND owner_id=%s
                UNION
                SELECT 1 FROM workspace_members WHERE workspace_id=%s AND user_id=%s AND status='active'
            """, (workspace_id, user_id, workspace_id, user_id))
            return cur.fetchone() is not None

def get_workspace_role(workspace_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM workspaces WHERE id=%s AND owner_id=%s", (workspace_id, user_id))
            if cur.fetchone():
                return 'owner'
            cur.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s AND status='active'", (workspace_id, user_id))
            row = cur.fetchone()
            return row[0] if row else None


def add_doc_to_workspace(workspace_id, doc_id, added_by):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workspace_documents (workspace_id,doc_id,added_by) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (workspace_id, doc_id, added_by)
            )
        conn.commit()

def remove_doc_from_workspace(workspace_id, doc_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM workspace_documents WHERE workspace_id=%s AND doc_id=%s", (workspace_id, doc_id))
        conn.commit()

def get_workspace_documents(workspace_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT d.*, u.name AS uploaded_by_name, wd.added_at
                   FROM documents d
                   JOIN workspace_documents wd ON wd.doc_id=d.id
                   JOIN users u ON u.id=d.user_id
                   WHERE wd.workspace_id=%s ORDER BY wd.added_at DESC""",
                (workspace_id,)
            )
            return _row(cur, one=False)


# Message Comments

def add_comment(message_id, user_id, content):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO message_comments (message_id,user_id,content) VALUES (%s,%s,%s) RETURNING *",
                (message_id, user_id, content)
            )
            row = _row(cur)
        conn.commit()
    return row

def get_comments(message_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT mc.*, u.name AS user_name
                   FROM message_comments mc JOIN users u ON u.id=mc.user_id
                   WHERE mc.message_id=%s ORDER BY mc.created_at ASC""",
                (message_id,)
            )
            return _row(cur, one=False)

def delete_comment(comment_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM message_comments WHERE id=%s AND user_id=%s", (comment_id, user_id))
        conn.commit()


# Activity Log

def log_activity(user_id, action, target_type='', target_id=None, target_name='', workspace_id=None):
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO activity_log (user_id,workspace_id,action,target_type,target_id,target_name) VALUES (%s,%s,%s,%s,%s,%s)",
                    (user_id, workspace_id, action, target_type, target_id, target_name)
                )
            conn.commit()
    except Exception as e:
        print(f"[Activity] log failed: {e}")

def get_activity(user_id, workspace_id=None, limit=50):
    with _conn() as conn:
        with conn.cursor() as cur:
            if workspace_id:
                cur.execute(
                    """SELECT al.*, u.name AS user_name FROM activity_log al
                       JOIN users u ON u.id=al.user_id
                       WHERE al.workspace_id=%s ORDER BY al.created_at DESC LIMIT %s""",
                    (workspace_id, limit)
                )
            else:
                cur.execute(
                    """SELECT al.*, u.name AS user_name FROM activity_log al
                       JOIN users u ON u.id=al.user_id
                       WHERE al.user_id=%s ORDER BY al.created_at DESC LIMIT %s""",
                    (user_id, limit)
                )
            return _row(cur, one=False)


# Enhanced Analytics

def get_analytics_extended(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents WHERE user_id=%s", (user_id,))
            docs = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(chunks),0) FROM documents WHERE user_id=%s", (user_id,))
            chunks = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(pages),0) FROM documents WHERE user_id=%s", (user_id,))
            pages = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chats WHERE user_id=%s", (user_id,))
            chats = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM messages m JOIN chats c ON m.chat_id=c.id WHERE c.user_id=%s AND m.role='user'",
                (user_id,)
            )
            queries = cur.fetchone()[0]
            cur.execute(
                """SELECT DATE(m.created_at) AS day, COUNT(*) AS cnt
                   FROM messages m JOIN chats c ON m.chat_id=c.id
                   WHERE c.user_id=%s AND m.role='user'
                     AND m.created_at >= NOW() - INTERVAL '7 days'
                   GROUP BY day ORDER BY day ASC""",
                (user_id,)
            )
            daily = _row(cur, one=False)
            cur.execute(
                "SELECT orig_name, chunks, pages, file_type, created_at FROM documents WHERE user_id=%s ORDER BY chunks DESC LIMIT 5",
                (user_id,)
            )
            top_docs = _row(cur, one=False)
            cur.execute(
                """SELECT rating, COUNT(*) AS cnt FROM message_feedback mf
                   JOIN messages m ON m.id=mf.message_id
                   JOIN chats c ON c.id=m.chat_id
                   WHERE c.user_id=%s GROUP BY rating""",
                (user_id,)
            )
            feedback_rows = _row(cur, one=False)
            feedback = {str(r['rating']): r['cnt'] for r in (feedback_rows or [])}
    return {
        "docs": docs, "chunks": chunks, "pages": pages,
        "chats": chats, "queries": queries,
        "daily_queries": daily or [],
        "top_docs": top_docs or [],
        "feedback": feedback,
    }


def get_analytics_full(user_id):
    """Full analytics: usage dashboard, page heatmap, topic clusters, quality trend."""
    with _conn() as conn:
        with conn.cursor() as cur:
            # ── Queries per day (last 30 days) ──────────────────────
            cur.execute("""
                SELECT DATE(m.created_at) AS day, COUNT(*) AS cnt
                FROM messages m JOIN chats c ON m.chat_id=c.id
                WHERE c.user_id=%s AND m.role='user'
                  AND m.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY day ORDER BY day ASC
            """, (user_id,))
            daily_30 = _row(cur, one=False)

            # ── Top documents by reference count (from sources JSON) ─
            cur.execute("""
                SELECT d.orig_name, d.pages, d.chunks,
                       COUNT(m.id) AS ref_count
                FROM documents d
                LEFT JOIN messages m ON m.sources LIKE '%%' || d.orig_name || '%%'
                    AND m.chat_id IN (SELECT id FROM chats WHERE user_id=%s)
                WHERE d.user_id=%s
                GROUP BY d.id, d.orig_name, d.pages, d.chunks
                ORDER BY ref_count DESC LIMIT 10
            """, (user_id, user_id))
            top_by_refs = _row(cur, one=False)

            # ── Page heatmap: which pages get cited most ─────────────
            # sources stored as JSON array: [{"file":..,"page":..}, ...]
            cur.execute("""
                SELECT m.sources FROM messages m
                JOIN chats c ON c.id=m.chat_id
                WHERE c.user_id=%s AND m.sources IS NOT NULL AND m.sources != 'null'
                ORDER BY m.created_at DESC LIMIT 500
            """, (user_id,))
            source_rows = cur.fetchall()

            # ── Quality trend: feedback over last 30 days ────────────
            cur.execute("""
                SELECT DATE(mf.created_at) AS day,
                       SUM(CASE WHEN mf.rating=1 THEN 1 ELSE 0 END) AS pos,
                       SUM(CASE WHEN mf.rating=-1 THEN 1 ELSE 0 END) AS neg
                FROM message_feedback mf
                JOIN messages m ON m.id=mf.message_id
                JOIN chats c ON c.id=m.chat_id
                WHERE c.user_id=%s
                  AND mf.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY day ORDER BY day ASC
            """, (user_id,))
            quality_trend = _row(cur, one=False)

            # ── Most asked topics (top words from user questions) ────
            cur.execute("""
                SELECT m.content FROM messages m
                JOIN chats c ON c.id=m.chat_id
                WHERE c.user_id=%s AND m.role='user'
                ORDER BY m.created_at DESC LIMIT 200
            """, (user_id,))
            question_rows = cur.fetchall()

    # Build page heatmap from source JSON
    import json as _json
    page_counts = {}
    for (src,) in source_rows:
        try:
            items = _json.loads(src) if src else []
            for item in (items if isinstance(items, list) else []):
                key = f"{item.get('file','?')} p.{item.get('page','?')}"
                page_counts[key] = page_counts.get(key, 0) + 1
        except Exception:
            pass
    heatmap = sorted(page_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    # Build topic word cloud from questions
    import re as _re
    STOPWORDS = {'what','is','the','a','an','of','in','to','how','does','do','can',
                 'are','was','were','be','been','being','have','has','had','will',
                 'would','could','should','may','might','shall','and','or','but',
                 'for','with','about','from','that','this','it','its','my','your',
                 'me','i','we','us','they','them','he','she','on','at','by','as',
                 'not','no','so','if','then','than','when','where','which','who'}
    word_counts = {}
    for (q,) in question_rows:
        for w in _re.findall(r'\b[a-z]{3,}\b', (q or '').lower()):
            if w not in STOPWORDS:
                word_counts[w] = word_counts.get(w, 0) + 1
    topics = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:30]

    return {
        "daily_30": daily_30 or [],
        "top_by_refs": top_by_refs or [],
        "heatmap": [{"key": k, "count": v} for k, v in heatmap],
        "quality_trend": quality_trend or [],
        "topics": [{"word": w, "count": c} for w, c in topics],
    }


def get_analytics_csv(user_id):
    """Return raw data rows for CSV export."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DATE(m.created_at) AS day, COUNT(*) AS queries
                FROM messages m JOIN chats c ON m.chat_id=c.id
                WHERE c.user_id=%s AND m.role='user'
                GROUP BY day ORDER BY day ASC
            """, (user_id,))
            daily = _row(cur, one=False)

            cur.execute("""
                SELECT d.orig_name, d.file_type, d.pages, d.chunks, d.file_size, d.created_at
                FROM documents d WHERE d.user_id=%s ORDER BY d.created_at DESC
            """, (user_id,))
            docs = _row(cur, one=False)

            cur.execute("""
                SELECT DATE(mf.created_at) AS day,
                       SUM(CASE WHEN mf.rating=1 THEN 1 ELSE 0 END) AS thumbs_up,
                       SUM(CASE WHEN mf.rating=-1 THEN 1 ELSE 0 END) AS thumbs_down
                FROM message_feedback mf
                JOIN messages m ON m.id=mf.message_id
                JOIN chats c ON c.id=m.chat_id
                WHERE c.user_id=%s GROUP BY day ORDER BY day ASC
            """, (user_id,))
            feedback = _row(cur, one=False)

    return {"daily": daily or [], "docs": docs or [], "feedback": feedback or []}


# ── Tier limits ────────────────────────────────────────────────────

TIER_LIMITS = {
    "free":       {"docs": 5,   "queries_per_day": 20,  "workspaces": 1},
    "pro":        {"docs": 50,  "queries_per_day": 200, "workspaces": 10},
    "enterprise": {"docs": 999, "queries_per_day": 9999,"workspaces": 999},
}

def get_tier_limits(tier):
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"])

def get_user_tier(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tier FROM users WHERE id=%s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else "free"

def set_user_tier(user_id, tier):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET tier=%s WHERE id=%s", (tier, user_id))
        conn.commit()

def count_user_queries_today(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM messages m JOIN chats c ON c.id=m.chat_id
                WHERE c.user_id=%s AND m.role='user'
                  AND m.created_at >= CURRENT_DATE
            """, (user_id,))
            return cur.fetchone()[0]

def check_tier_limit(user_id, resource):
    """Returns (allowed: bool, limit: int, current: int)."""
    tier = get_user_tier(user_id)
    limits = get_tier_limits(tier)
    if resource == "queries":
        current = count_user_queries_today(user_id)
        limit = limits["queries_per_day"]
        return current < limit, limit, current
    if resource == "docs":
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM documents WHERE user_id=%s", (user_id,))
                current = cur.fetchone()[0]
        limit = limits["docs"]
        return current < limit, limit, current
    return True, 999, 0


# ── API Keys ───────────────────────────────────────────────────────

def create_api_key(user_id, label="Default"):
    import secrets, hashlib
    raw = "lx_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    prefix = raw[:10]
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO api_keys (user_id,key_hash,key_prefix,label) VALUES (%s,%s,%s,%s) RETURNING id,key_prefix,label,created_at",
                (user_id, key_hash, prefix, label)
            )
            row = _row(cur)
        conn.commit()
    row["raw_key"] = raw  # only returned once
    return row

def get_user_api_keys(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,key_prefix,label,last_used,created_at FROM api_keys WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,)
            )
            return _row(cur, one=False)

def delete_api_key(key_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM api_keys WHERE id=%s AND user_id=%s", (key_id, user_id))
        conn.commit()

def get_user_by_api_key(raw_key):
    import hashlib
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.* FROM users u
                JOIN api_keys ak ON ak.user_id=u.id
                WHERE ak.key_hash=%s
            """, (key_hash,))
            user = _row(cur)
            if user:
                cur.execute("UPDATE api_keys SET last_used=NOW() WHERE key_hash=%s", (key_hash,))
            conn.commit()
    return user


# ── Admin ──────────────────────────────────────────────────────────

def get_all_users(limit=100, offset=0):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.name, u.email, u.tier, u.is_admin, u.created_at,
                       COUNT(DISTINCT d.id) AS doc_count,
                       COUNT(DISTINCT c.id) AS chat_count
                FROM users u
                LEFT JOIN documents d ON d.user_id=u.id
                LEFT JOIN chats c ON c.user_id=u.id
                GROUP BY u.id ORDER BY u.created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            return _row(cur, one=False)

def get_platform_stats():
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM documents")
            total_docs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM messages WHERE role='user'")
            total_queries = cur.fetchone()[0]
            cur.execute("SELECT tier, COUNT(*) FROM users GROUP BY tier")
            tier_rows = cur.fetchall()
            tiers = {r[0]: r[1] for r in tier_rows}
    return {"total_users": total_users, "total_docs": total_docs,
            "total_queries": total_queries, "tiers": tiers}

def admin_set_tier(target_user_id, tier):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET tier=%s WHERE id=%s", (tier, target_user_id))
        conn.commit()

def admin_delete_user(target_user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id=%s", (target_user_id,))
        conn.commit()


# ── White-label ────────────────────────────────────────────────────

def get_white_label(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM white_label WHERE user_id=%s", (user_id,))
            return _row(cur)

def save_white_label(user_id, app_name, logo_url, primary_color):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO white_label (user_id,app_name,logo_url,primary_color)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (user_id) DO UPDATE
                SET app_name=%s, logo_url=%s, primary_color=%s
            """, (user_id, app_name, logo_url, primary_color,
                  app_name, logo_url, primary_color))
        conn.commit()


# ── Webhooks ───────────────────────────────────────────────────────

def create_webhook(user_id, url, events='document_uploaded,query_made', secret=''):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO webhooks (user_id,url,events,secret) VALUES (%s,%s,%s,%s) RETURNING *",
                (user_id, url, events, encrypt_value(secret))
            )
            row = _row(cur)
        conn.commit()
    return row

def get_user_webhooks(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM webhooks WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
            return _row(cur, one=False)

def delete_webhook(webhook_id, user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM webhooks WHERE id=%s AND user_id=%s", (webhook_id, user_id))
        conn.commit()

def get_active_webhooks(user_id, event):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM webhooks WHERE user_id=%s AND active=TRUE AND events LIKE %s",
                (user_id, f'%{event}%')
            )
            return _row(cur, one=False)


# ── Rate Limiting & Security ────────────────────────────────────────

def get_auth_lockout_until(keys):
    """
    Checks if any of the keys are currently locked out.
    Returns the maximum lockout_until timestamp if in the future, or None.
    """
    if not keys:
        return None
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT lockout_until FROM auth_failures WHERE key = ANY(%s) AND lockout_until > NOW()",
                (keys,)
            )
            rows = cur.fetchall()
            if rows:
                return max(r[0] for r in rows)
    return None

def record_auth_failure(keys, base_secs, factor, max_secs):
    """
    Increments failed auth attempts for the provided keys and computes the lockout delay.
    """
    if not keys:
        return
    with _conn() as conn:
        with conn.cursor() as cur:
            for key in keys:
                cur.execute("SELECT attempts FROM auth_failures WHERE key = %s", (key,))
                row = cur.fetchone()
                attempts = row[0] + 1 if row else 1
                
                # Exponential backoff: Base * (Factor ^ (attempts - 1))
                delay = min(base_secs * (factor ** (attempts - 1)), max_secs)
                
                cur.execute("""
                    INSERT INTO auth_failures (key, attempts, last_failed_at, lockout_until)
                    VALUES (%s, %s, NOW(), NOW() + (%s * INTERVAL '1 second'))
                    ON CONFLICT (key) DO UPDATE SET
                        attempts = EXCLUDED.attempts,
                        last_failed_at = EXCLUDED.last_failed_at,
                        lockout_until = EXCLUDED.lockout_until
                """, (key, attempts, int(delay)))
        conn.commit()

def clear_auth_failures(keys):
    """
    Clears failed auth attempt records for the provided keys.
    """
    if not keys:
        return
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM auth_failures WHERE key = ANY(%s)", (keys,))
        conn.commit()

def check_sliding_window_rate_limit(key, limit, window_secs):
    """
    Checks and updates the sliding rate limit window for a given key.
    Returns True if rate limit is exceeded, False otherwise.
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            # Delete expired entries
            cur.execute(
                "DELETE FROM rate_limits WHERE window_start < NOW() - (%s * INTERVAL '1 second')",
                (int(window_secs),)
            )
            
            cur.execute("SELECT requests, window_start FROM rate_limits WHERE key = %s", (key,))
            row = cur.fetchone()
            if row:
                requests, start_time = row
                if requests >= limit:
                    return True
                cur.execute("UPDATE rate_limits SET requests = requests + 1 WHERE key = %s", (key,))
            else:
                cur.execute(
                    "INSERT INTO rate_limits (key, requests, window_start) VALUES (%s, 1, NOW())",
                    (key,)
                )
        conn.commit()
    return False


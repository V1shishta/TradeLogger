"""Storage layer for Trade Journal Pro — dual backend.

Runs on **SQLite** locally (zero dependencies, `python run.py`) and on
**Postgres** when a connection URL is present in the environment (e.g. Vercel
Postgres / Neon in production). A thin connection wrapper hides the differences
so the rest of the app is written once:

  * `?` placeholders are rewritten to `%s` for Postgres automatically.
  * `conn.insert(sql, params)` returns the new row id on both engines
    (`RETURNING id` on Postgres, `lastrowid` on SQLite).
  * Rows come back as plain dicts on both engines.

The metrics, coach, CSV and API layers never touch engine-specific SQL.
"""
import os
import sqlite3
import threading

# --- backend selection -----------------------------------------------------
# Vercel Postgres / Neon expose several URLs; prefer a direct (non-pooled) one.
DATABASE_URL = (
    os.environ.get("POSTGRES_URL_NON_POOLING")
    or os.environ.get("POSTGRES_URL")
    or os.environ.get("DATABASE_URL")
)
IS_PG = bool(DATABASE_URL)

DB_PATH = os.environ.get(
    "TJP_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tradejournal.db"),
)

_lock = threading.Lock()

if IS_PG:
    import psycopg
    from psycopg.rows import dict_row


# ---------------------------------------------------------------------------
# Connection wrapper — uniform API over sqlite3 and psycopg
# ---------------------------------------------------------------------------
class Conn:
    def __init__(self, raw, is_pg):
        self.raw = raw
        self.is_pg = is_pg

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.is_pg else sql

    def execute(self, sql, params=()):
        if self.is_pg:
            cur = self.raw.cursor()
            cur.execute(self._sql(sql), params)
            return cur
        return self.raw.execute(sql, params)

    def executemany(self, sql, seq):
        if self.is_pg:
            cur = self.raw.cursor()
            cur.executemany(self._sql(sql), seq)
            return cur
        return self.raw.executemany(sql, seq)

    def insert(self, sql, params=()):
        """Run an INSERT (written without RETURNING) and return the new id."""
        if self.is_pg:
            cur = self.raw.cursor()
            cur.execute(self._sql(sql) + " RETURNING id", params)
            return cur.fetchone()["id"]
        cur = self.raw.execute(sql, params)
        return cur.lastrowid

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def get_conn():
    if IS_PG:
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return Conn(raw, True)
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    return Conn(raw, False)


# ---------------------------------------------------------------------------
# Schema (per-engine)
# ---------------------------------------------------------------------------
def _schema():
    pk = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    real = "DOUBLE PRECISION" if IS_PG else "REAL"
    ts = "TIMESTAMPTZ DEFAULT now()" if IS_PG else "TEXT DEFAULT (datetime('now'))"
    return [
        f"""CREATE TABLE IF NOT EXISTS users (
            id {pk},
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            pw_salt TEXT NOT NULL,
            trader_type TEXT DEFAULT '',
            experience TEXT DEFAULT '',
            account_size {real} DEFAULT 0,
            base_currency TEXT DEFAULT 'USD',
            onboarded INTEGER DEFAULT 0,
            created_at {ts}
        )""",
        f"""CREATE TABLE IF NOT EXISTS trades (
            id {pk},
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            instrument TEXT DEFAULT 'equity',
            direction TEXT DEFAULT 'long',
            quantity {real} NOT NULL,
            entry_price {real} NOT NULL,
            exit_price {real},
            stop_price {real},
            fees {real} DEFAULT 0,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            strategy TEXT DEFAULT '',
            setup TEXT DEFAULT '',
            market_condition TEXT DEFAULT '',
            timeframe TEXT DEFAULT '',
            session TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            pre_notes TEXT DEFAULT '',
            post_notes TEXT DEFAULT '',
            emotion TEXT DEFAULT '',
            rating INTEGER DEFAULT 0,
            screenshot TEXT DEFAULT '',
            created_at {ts}
        )""",
        "CREATE INDEX IF NOT EXISTS idx_trades_user ON trades(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_trades_entry ON trades(user_id, entry_time)",
        f"""CREATE TABLE IF NOT EXISTS goals (
            id {pk},
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            metric TEXT DEFAULT 'custom',
            target {real} DEFAULT 0,
            current {real} DEFAULT 0,
            deadline TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at {ts}
        )""",
        f"""CREATE TABLE IF NOT EXISTS habits (
            id {pk},
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            log TEXT DEFAULT '{{}}',
            created_at {ts}
        )""",
    ]


def init_db():
    with _lock:
        conn = get_conn()
        try:
            for stmt in _schema():
                conn.execute(stmt)
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# One-time readiness (used by the serverless entry point)
# ---------------------------------------------------------------------------
_ready = False


def ensure_ready():
    """Idempotently create the schema and (optionally) seed a demo account.

    Safe to call on every request: it short-circuits once a warm instance is
    initialized. On serverless cold starts it builds the schema on first hit."""
    global _ready
    if _ready:
        return
    init_db()
    if os.environ.get("AUTO_SEED", "1") != "0":
        try:
            from . import seed
            seed.seed_if_empty()
        except Exception as e:  # never let seeding break the request
            print("Demo seed skipped:", e)
    _ready = True


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------
def row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return {k: row[k] for k in row.keys()}


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]

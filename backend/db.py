"""SQLite storage layer for Trade Journal Pro.

Uses only the Python standard library. A single database file holds users,
trades, journal media, goals, and habits. Connections are opened per-request
(SQLite handles this cleanly) with row access by column name.
"""
import os
import sqlite3
import threading

DB_PATH = os.environ.get(
    "TJP_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tradejournal.db"),
)

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    pw_hash       TEXT NOT NULL,
    pw_salt       TEXT NOT NULL,
    -- onboarding profile
    trader_type   TEXT DEFAULT '',      -- intraday / swing / options / futures / crypto
    experience    TEXT DEFAULT '',      -- beginner / intermediate / advanced
    account_size  REAL DEFAULT 0,
    base_currency TEXT DEFAULT 'USD',
    onboarded     INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    symbol          TEXT NOT NULL,
    instrument      TEXT DEFAULT 'equity',   -- equity/option/future/crypto/forex
    direction       TEXT DEFAULT 'long',     -- long/short
    quantity        REAL NOT NULL,
    entry_price     REAL NOT NULL,
    exit_price      REAL,                    -- null => open position
    stop_price      REAL,                    -- for R-multiple / risk
    fees            REAL DEFAULT 0,
    entry_time      TEXT NOT NULL,           -- ISO datetime
    exit_time       TEXT,
    strategy        TEXT DEFAULT '',
    setup           TEXT DEFAULT '',
    market_condition TEXT DEFAULT '',        -- trending/ranging/volatile
    timeframe       TEXT DEFAULT '',         -- 1m/5m/1h/daily...
    session         TEXT DEFAULT '',         -- pre-market/open/midday/close/overnight
    tags            TEXT DEFAULT '',         -- comma separated
    pre_notes       TEXT DEFAULT '',
    post_notes      TEXT DEFAULT '',
    emotion         TEXT DEFAULT '',         -- calm/fomo/fear/greed/revenge/confident
    rating          INTEGER DEFAULT 0,       -- self-graded execution 1-5
    screenshot      TEXT DEFAULT '',         -- data URL or path
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_trades_user ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_entry ON trades(user_id, entry_time);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    title       TEXT NOT NULL,
    metric      TEXT DEFAULT 'custom',   -- win_rate/pnl/profit_factor/discipline/custom
    target      REAL DEFAULT 0,
    current     REAL DEFAULT 0,
    deadline    TEXT DEFAULT '',
    status      TEXT DEFAULT 'active',   -- active/done/archived
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS habits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    name        TEXT NOT NULL,           -- e.g. "Followed trading plan"
    log         TEXT DEFAULT '{}',       -- json {date: bool}
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _lock:
        conn = get_conn()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row is not None else None


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]

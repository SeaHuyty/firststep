"""SQLite sandbox: sessions, proposals and the paper account.

No SQL exists outside app/store. Following the Python sqlite3 docs, a
short-lived connection is opened per unit of work (connections are not
shared between threads), `with con:` commits or rolls back, and every
query uses ? placeholders. Money is stored as decimal text.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  persona TEXT,
  stage TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  sim_month TEXT NOT NULL,
  sim_offset_hours REAL NOT NULL DEFAULT 0,
  audit_head TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  role TEXT NOT NULL CHECK (role IN ('user', 'sprout')),
  text TEXT NOT NULL,
  cards_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  kind TEXT NOT NULL,
  contents_json TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'executed', 'superseded')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS used_nonces (
  nonce TEXT PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  used_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cash (
  session_id TEXT PRIMARY KEY REFERENCES sessions(id),
  balance TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
  session_id TEXT NOT NULL REFERENCES sessions(id),
  product_id TEXT NOT NULL,
  units TEXT NOT NULL,
  PRIMARY KEY (session_id, product_id)
);
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  proposal_id TEXT,
  product_id TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
  amount TEXT NOT NULL,
  units TEXT NOT NULL,
  nav TEXT NOT NULL,
  sim_month TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('user', 'auto_invest', 'rebalance')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auto_invest (
  session_id TEXT PRIMARY KEY REFERENCES sessions(id),
  monthly TEXT NOT NULL,
  weights_json TEXT NOT NULL,
  next_month TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS value_history (
  session_id TEXT NOT NULL REFERENCES sessions(id),
  sim_month TEXT NOT NULL,
  value TEXT NOT NULL,
  PRIMARY KEY (session_id, sim_month)
);
CREATE TABLE IF NOT EXISTS cooling_off (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  product_id TEXT NOT NULL,
  amount TEXT NOT NULL,
  until_hours REAL NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('waiting', 'released', 'cancelled'))
);
"""


class Store:
    """Opens connections to one sandbox database file."""

    def __init__(self, path: Path) -> None:
        """Create the database and its tables if they do not exist."""
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con:
            con.execute("PRAGMA journal_mode=WAL")  # readers don't block the writer
            con.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection inside one transaction, then close it."""
        with closing(self._connect()) as con, con:
            yield con

"""SQLite record of every source file, so re-running never repeats work or posts twice.

Status flow: new -> rendered -> in_review -> approved -> scheduled -> published,
or failed with `error` set.
"""
import hashlib
import json
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL,              -- 'ktck' | 'trend'
    src_path     TEXT NOT NULL,
    fingerprint  TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT 'new',
    consent      INTEGER NOT NULL DEFAULT 0, -- 1 only when the source sat in duoc-dang/
    meta         TEXT NOT NULL DEFAULT '{}', -- parsed name info as JSON
    output_path  TEXT,
    fb_id        TEXT,
    scheduled_at TEXT,
    error        TEXT,
    updated_at   REAL NOT NULL
)
"""
CHUNK = 4 * 1024 * 1024


def connect(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute(SCHEMA)
    return db


def fingerprint(path):
    """Size plus the first and last 4 MB: identifies a 1 GB recording without reading it all,
    which matters because Drive streams each byte read over the network."""
    size = os.path.getsize(path)
    h = hashlib.sha1(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(CHUNK))
        if size > CHUNK:
            f.seek(max(CHUNK, size - CHUNK))
            h.update(f.read(CHUNK))
    return h.hexdigest()


def find(db, fp):
    return db.execute("SELECT * FROM items WHERE fingerprint = ?", (fp,)).fetchone()


def add(db, kind, src_path, fp, consent, meta):
    cur = db.execute(
        "INSERT INTO items (kind, src_path, fingerprint, consent, meta, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (kind, src_path, fp, int(consent), json.dumps(meta, ensure_ascii=False), time.time()))
    db.commit()
    return cur.lastrowid


def update(db, item_id, **fields):
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE items SET {cols} WHERE id = ?", (*fields.values(), item_id))
    db.commit()


def by_status(db, status, kind=None):
    sql, args = "SELECT * FROM items WHERE status = ?", [status]
    if kind:
        sql, args = sql + " AND kind = ?", args + [kind]
    return db.execute(sql + " ORDER BY id", args).fetchall()

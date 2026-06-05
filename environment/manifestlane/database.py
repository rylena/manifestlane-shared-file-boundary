import sqlite3
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db_path = Path(current_app.config["DATABASE"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    storage_dir = Path(current_app.config["STORAGE_DIR"])
    storage_dir.mkdir(parents=True, exist_ok=True)

    db = get_db()
    db.executescript(SCHEMA)
    seeded = db.execute("SELECT COUNT(*) AS count FROM companies").fetchone()["count"]
    if seeded:
        return

    _seed_files(storage_dir)
    _seed_rows(db)
    db.commit()


def _seed_files(storage_dir):
    files = {
        "northstar-packing-memo.txt": (
            "Northstar packing memo\n"
            "Seal: NS-4492\n"
            "Contents: chilled medical packaging inserts\n"
        ),
        "northstar-fumigation-note.txt": (
            "Northstar fumigation note\n"
            "Dock release: N-17\n"
        ),
        "blueharbor-packing-memo.txt": (
            "Blue Harbor packing memo\n"
            "Seal: BH-8814\n"
            "Contents: retail appliance cartons\n"
        ),
        "blueharbor-invoice-note.txt": (
            "Blue Harbor invoice note\n"
            "Payment window: net 15\n"
        ),
    }
    for name, content in files.items():
        (storage_dir / name).write_text(content, encoding="utf-8")


def _seed_rows(db):
    db.executemany(
        "INSERT INTO companies (id, slug, name) VALUES (?, ?, ?)",
        [
            (1, "northstar", "Northstar Medical Logistics"),
            (2, "blueharbor", "Blue Harbor Retail Group"),
        ],
    )
    db.executemany(
        """
        INSERT INTO users
            (id, company_id, username, password_hash, display_name, role)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                1,
                "reviewer",
                generate_password_hash("manifestlane-review"),
                "Riley Reviewer",
                "ops_reviewer",
            ),
            (
                2,
                1,
                "dispatcher",
                generate_password_hash("manifestlane-dispatch"),
                "Drew Dispatcher",
                "dispatcher",
            ),
            (
                3,
                2,
                "partner",
                generate_password_hash("manifestlane-partner"),
                "Pat Partner",
                "partner_admin",
            ),
        ],
    )
    db.executemany(
        """
        INSERT INTO api_tokens (id, user_id, token, label, active)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, 1, "ml-review-token-9f1c1b", "review automation", 1),
            (2, 3, "ml-partner-token-771d9a", "partner import", 1),
        ],
    )
    db.executemany(
        """
        INSERT INTO documents
            (id, company_id, reference, vessel, status, destination, eta, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (101, 1, "NS-2026-0419", "MV Larkspur", "ready", "Jebel Ali", "2026-06-07", 1),
            (102, 1, "NS-2026-0440", "MV Meridian", "review", "Sohar", "2026-06-12", 2),
            (201, 2, "BH-2026-1182", "MV Cantara", "ready", "Khalifa Port", "2026-06-08", 3),
            (202, 2, "BH-2026-1199", "MV Pelican", "hold", "Hamad Port", "2026-06-15", 3),
        ],
    )
    db.executemany(
        """
        INSERT INTO attachments
            (id, document_id, filename, content_type, storage_name, byte_length, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1001, 101, "packing-memo.txt", "text/plain", "northstar-packing-memo.txt", 84, 1),
            (1002, 102, "fumigation-note.txt", "text/plain", "northstar-fumigation-note.txt", 48, 2),
            (2001, 201, "packing-memo.txt", "text/plain", "blueharbor-packing-memo.txt", 82, 3),
            (2002, 202, "invoice-note.txt", "text/plain", "blueharbor-invoice-note.txt", 51, 3),
        ],
    )
    db.executemany(
        """
        INSERT INTO share_links (code, document_id, created_by, expires_at, active)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            ("share-ns-0419", 101, 1, "2026-12-31", 1),
            ("share-bh-1182", 201, 3, "2026-12-31", 1),
        ],
    )


SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL,
    reference TEXT NOT NULL,
    vessel TEXT NOT NULL,
    status TEXT NOT NULL,
    destination TEXT NOT NULL,
    eta TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    storage_name TEXT NOT NULL,
    byte_length INTEGER NOT NULL,
    uploaded_by INTEGER NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS share_links (
    code TEXT PRIMARY KEY,
    document_id INTEGER NOT NULL,
    created_by INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    document_id INTEGER NOT NULL,
    attachment_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

import io
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from werkzeug.security import generate_password_hash


APP_ROOT = Path(os.environ.get("APP_UNDER_TEST", "/app/manifestlane"))
sys.path.insert(0, str(APP_ROOT.parent))

from manifestlane.app import create_app
from manifestlane.database import get_db


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MANIFESTLANE_DB", str(tmp_path / "manifestlane.sqlite"))
    monkeypatch.setenv("MANIFESTLANE_STORAGE", str(tmp_path / "files"))
    monkeypatch.setenv("MANIFESTLANE_SECRET", "test-secret")
    return create_app(testing=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username="reviewer", password="manifestlane-review"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def query_one(app, sql, params=()):
    with app.app_context():
        row = get_db().execute(sql, params).fetchone()
        assert row is not None
        return dict(row)


def test_shared_file_link_only_serves_files_from_the_shared_document(app, client):
    shared = query_one(
        app,
        """
        SELECT share_links.code, documents.id AS document_id
        FROM share_links
        JOIN documents ON documents.id = share_links.document_id
        JOIN companies ON companies.id = documents.company_id
        WHERE companies.slug = 'blueharbor'
        """,
    )
    allowed = query_one(
        app,
        "SELECT id FROM attachments WHERE document_id = ? ORDER BY id LIMIT 1",
        (shared["document_id"],),
    )
    other = query_one(
        app,
        """
        SELECT attachments.id
        FROM attachments
        JOIN documents ON documents.id = attachments.document_id
        JOIN companies ON companies.id = documents.company_id
        WHERE companies.slug = 'northstar'
        ORDER BY attachments.id
        LIMIT 1
        """,
    )

    ok = client.get(f"/shares/{shared['code']}/attachments/{allowed['id']}")
    assert ok.status_code == 200
    assert b"Blue Harbor packing memo" in ok.data

    leaked = client.get(f"/shares/{shared['code']}/attachments/{other['id']}")
    assert leaked.status_code in {403, 404}
    assert b"Northstar packing memo" not in leaked.data
    assert b"Seal: NS-4492" not in leaked.data


def test_api_download_binds_attachment_to_requested_document_with_dynamic_records(app, client):
    ids = make_dynamic_records(app)

    ok = client.get(
        f"/api/v1/documents/{ids['owned_doc_id']}/attachments/{ids['owned_attachment_id']}",
        headers={"Authorization": f"Bearer {ids['token']}"},
    )
    assert ok.status_code == 200
    assert ids["owned_content"].encode() in ok.data

    leaked = client.get(
        f"/api/v1/documents/{ids['owned_doc_id']}/attachments/{ids['foreign_attachment_id']}",
        headers={"Authorization": f"Bearer {ids['token']}"},
    )
    assert leaked.status_code in {403, 404}
    assert ids["foreign_content"].encode() not in leaked.data


def test_signed_in_downloads_and_uploads_keep_company_file_boundaries(app, client):
    login_response = login(client)
    assert login_response.status_code == 200
    assert b"Northstar Medical Logistics documents" in login_response.data

    search = client.get("/search?q=Larkspur")
    assert search.status_code == 200
    assert b"NS-2026-0419" in search.data

    upload = client.post(
        "/documents/101/attachments",
        data={"file": (io.BytesIO(b"Uploaded review memo\nSeal: NS-UPLOAD\n"), "review-memo.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload.status_code == 200
    assert b"review-memo.txt" in upload.data

    new_attachment = query_one(
        app,
        "SELECT id FROM attachments WHERE filename = 'review-memo.txt' ORDER BY id DESC LIMIT 1",
    )
    own_download = client.get(f"/documents/101/attachments/{new_attachment['id']}")
    assert own_download.status_code == 200
    assert b"Seal: NS-UPLOAD" in own_download.data

    foreign = query_one(
        app,
        """
        SELECT attachments.id
        FROM attachments
        JOIN documents ON documents.id = attachments.document_id
        JOIN companies ON companies.id = documents.company_id
        WHERE companies.slug = 'blueharbor'
        ORDER BY attachments.id
        LIMIT 1
        """,
    )
    leaked = client.get(f"/documents/101/attachments/{foreign['id']}")
    assert leaked.status_code in {403, 404}
    assert b"Blue Harbor packing memo" not in leaked.data
    assert b"Seal: BH-8814" not in leaked.data


def make_dynamic_records(app):
    suffix = uuid4().hex[:10]
    token = f"ml-dyn-{suffix}"
    owned_content = f"Owned dynamic memo {suffix}"
    foreign_content = f"Foreign dynamic memo {suffix}"
    with app.app_context():
        storage = Path(app.config["STORAGE_DIR"])
        storage.mkdir(parents=True, exist_ok=True)
        (storage / f"owned-{suffix}.txt").write_text(owned_content, encoding="utf-8")
        (storage / f"foreign-{suffix}.txt").write_text(foreign_content, encoding="utf-8")

        db = get_db()
        cursor = db.execute(
            "INSERT INTO companies (slug, name) VALUES (?, ?)",
            (f"owned-{suffix}", f"Owned Company {suffix}"),
        )
        owned_company = cursor.lastrowid
        cursor = db.execute(
            "INSERT INTO companies (slug, name) VALUES (?, ?)",
            (f"foreign-{suffix}", f"Foreign Company {suffix}"),
        )
        foreign_company = cursor.lastrowid
        cursor = db.execute(
            """
            INSERT INTO users (company_id, username, password_hash, display_name, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                owned_company,
                f"user-{suffix}",
                generate_password_hash("irrelevant"),
                f"Dynamic User {suffix}",
                "api",
            ),
        )
        user_id = cursor.lastrowid
        db.execute(
            "INSERT INTO api_tokens (user_id, token, label, active) VALUES (?, ?, ?, 1)",
            (user_id, token, "dynamic token"),
        )
        cursor = db.execute(
            """
            INSERT INTO documents (company_id, reference, vessel, status, destination, eta, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (owned_company, f"OWN-{suffix}", "MV Own", "ready", "Dubai", "2026-07-01", user_id),
        )
        owned_doc = cursor.lastrowid
        cursor = db.execute(
            """
            INSERT INTO documents (company_id, reference, vessel, status, destination, eta, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (foreign_company, f"FOR-{suffix}", "MV Foreign", "ready", "Abu Dhabi", "2026-07-02", user_id),
        )
        foreign_doc = cursor.lastrowid
        cursor = db.execute(
            """
            INSERT INTO attachments
                (document_id, filename, content_type, storage_name, byte_length, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (owned_doc, "owned.txt", "text/plain", f"owned-{suffix}.txt", len(owned_content), user_id),
        )
        owned_attachment = cursor.lastrowid
        cursor = db.execute(
            """
            INSERT INTO attachments
                (document_id, filename, content_type, storage_name, byte_length, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (foreign_doc, "foreign.txt", "text/plain", f"foreign-{suffix}.txt", len(foreign_content), user_id),
        )
        foreign_attachment = cursor.lastrowid
        db.commit()

    return {
        "token": token,
        "owned_doc_id": owned_doc,
        "owned_attachment_id": owned_attachment,
        "foreign_attachment_id": foreign_attachment,
        "owned_content": owned_content,
        "foreign_content": foreign_content,
    }

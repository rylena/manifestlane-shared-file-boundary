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
    ids = make_dynamic_records(app)

    ok = client.get(f"/shares/{ids['share_code']}/attachments/{ids['owned_attachment_id']}")
    assert ok.status_code == 200
    assert ids["owned_content"].encode() in ok.data

    leaked = client.get(f"/shares/{ids['share_code']}/attachments/{ids['foreign_attachment_id']}")
    assert leaked.status_code in {403, 404}
    assert ids["foreign_content"].encode() not in leaked.data


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
    ids = make_dynamic_records(app)

    login_response = login(client, ids["username"], ids["password"])
    assert login_response.status_code == 200
    assert ids["company_name"].encode() in login_response.data

    search = client.get(f"/search?q={ids['owned_vessel']}")
    assert search.status_code == 200
    assert ids["owned_reference"].encode() in search.data

    upload = client.post(
        f"/documents/{ids['owned_doc_id']}/attachments",
        data={
            "file": (
                io.BytesIO(ids["upload_content"].encode()),
                ids["upload_filename"],
            )
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload.status_code == 200
    assert ids["upload_filename"].encode() in upload.data

    new_attachment = query_one(
        app,
        "SELECT id FROM attachments WHERE filename = ? ORDER BY id DESC LIMIT 1",
        (ids["upload_filename"],),
    )
    own_download = client.get(f"/documents/{ids['owned_doc_id']}/attachments/{new_attachment['id']}")
    assert own_download.status_code == 200
    assert ids["upload_content"].encode() in own_download.data

    leaked = client.get(f"/documents/{ids['owned_doc_id']}/attachments/{ids['foreign_attachment_id']}")
    assert leaked.status_code in {403, 404}
    assert ids["foreign_content"].encode() not in leaked.data


def make_dynamic_records(app):
    suffix = uuid4().hex[:10]
    token = f"{uuid4().hex}.{uuid4().hex}"
    username = f"user-{suffix}"
    password = f"pass-{uuid4().hex[:12]}"
    company_name = f"Owned Company {suffix}"
    owned_reference = f"OWN-{suffix}"
    owned_vessel = f"Vessel-{suffix}"
    foreign_reference = f"FOR-{suffix}"
    share_code = f"s-{uuid4().hex}"
    owned_content = f"Owned dynamic memo {uuid4().hex}"
    foreign_content = f"Foreign dynamic memo {uuid4().hex}"
    upload_filename = f"review-{suffix}.txt"
    upload_content = f"Uploaded dynamic memo {uuid4().hex}\n"
    with app.app_context():
        storage = Path(app.config["STORAGE_DIR"])
        storage.mkdir(parents=True, exist_ok=True)
        (storage / f"owned-{suffix}.txt").write_text(owned_content, encoding="utf-8")
        (storage / f"foreign-{suffix}.txt").write_text(foreign_content, encoding="utf-8")

        db = get_db()
        cursor = db.execute(
            "INSERT INTO companies (slug, name) VALUES (?, ?)",
            (f"owned-{suffix}", company_name),
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
                username,
                generate_password_hash(password),
                f"Dynamic User {suffix}",
                "api",
            ),
        )
        user_id = cursor.lastrowid
        cursor = db.execute(
            """
            INSERT INTO users (company_id, username, password_hash, display_name, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                foreign_company,
                f"foreign-{suffix}",
                generate_password_hash("irrelevant"),
                f"Foreign User {suffix}",
                "api",
            ),
        )
        foreign_user_id = cursor.lastrowid
        db.execute(
            "INSERT INTO api_tokens (user_id, token, label, active) VALUES (?, ?, ?, 1)",
            (user_id, token, "dynamic token"),
        )
        cursor = db.execute(
            """
            INSERT INTO documents (company_id, reference, vessel, status, destination, eta, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (owned_company, owned_reference, owned_vessel, "ready", "Dubai", "2026-07-01", user_id),
        )
        owned_doc = cursor.lastrowid
        cursor = db.execute(
            """
            INSERT INTO documents (company_id, reference, vessel, status, destination, eta, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (foreign_company, foreign_reference, "MV Foreign", "ready", "Abu Dhabi", "2026-07-02", foreign_user_id),
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
        db.execute(
            """
            INSERT INTO share_links (code, document_id, created_by, expires_at, active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (share_code, owned_doc, user_id, "2027-01-01"),
        )
        db.commit()

    return {
        "token": token,
        "username": username,
        "password": password,
        "company_name": company_name,
        "owned_reference": owned_reference,
        "owned_vessel": owned_vessel,
        "share_code": share_code,
        "owned_doc_id": owned_doc,
        "owned_attachment_id": owned_attachment,
        "foreign_attachment_id": foreign_attachment,
        "owned_content": owned_content,
        "foreign_content": foreign_content,
        "upload_filename": upload_filename,
        "upload_content": upload_content,
    }

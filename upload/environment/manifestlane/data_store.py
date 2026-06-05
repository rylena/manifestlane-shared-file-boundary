import os
from pathlib import Path
from uuid import uuid4

from flask import current_app

from .database import get_db


def get_user_by_id(user_id):
    return get_db().execute(
        """
        SELECT users.*, companies.slug AS company_slug, companies.name AS company_name
        FROM users
        JOIN companies ON companies.id = users.company_id
        WHERE users.id = ?
        """,
        (user_id,),
    ).fetchone()


def get_user_by_username(username):
    return get_db().execute(
        """
        SELECT users.*, companies.slug AS company_slug, companies.name AS company_name
        FROM users
        JOIN companies ON companies.id = users.company_id
        WHERE users.username = ?
        """,
        (username,),
    ).fetchone()


def get_user_for_token(token):
    if not token:
        return None
    return get_db().execute(
        """
        SELECT users.*, companies.slug AS company_slug, companies.name AS company_name
        FROM api_tokens
        JOIN users ON users.id = api_tokens.user_id
        JOIN companies ON companies.id = users.company_id
        WHERE api_tokens.token = ? AND api_tokens.active = 1
        """,
        (token,),
    ).fetchone()


def list_documents_for_user(user):
    return get_db().execute(
        """
        SELECT documents.*, companies.name AS company_name
        FROM documents
        JOIN companies ON companies.id = documents.company_id
        WHERE documents.company_id = ?
        ORDER BY documents.id
        """,
        (user["company_id"],),
    ).fetchall()


def search_documents(user, query):
    like = f"%{query.strip()}%"
    return get_db().execute(
        """
        SELECT documents.*, companies.name AS company_name
        FROM documents
        JOIN companies ON companies.id = documents.company_id
        WHERE documents.company_id = ?
          AND (
            documents.reference LIKE ?
            OR documents.vessel LIKE ?
            OR documents.destination LIKE ?
          )
        ORDER BY documents.id
        """,
        (user["company_id"], like, like, like),
    ).fetchall()


def user_can_see_document(user, doc_id):
    row = get_db().execute(
        """
        SELECT 1
        FROM documents
        WHERE id = ? AND company_id = ?
        """,
        (doc_id, user["company_id"]),
    ).fetchone()
    return row is not None


def get_document_for_user(user, doc_id):
    return get_db().execute(
        """
        SELECT documents.*, companies.name AS company_name
        FROM documents
        JOIN companies ON companies.id = documents.company_id
        WHERE documents.id = ? AND documents.company_id = ?
        """,
        (doc_id, user["company_id"]),
    ).fetchone()


def get_document(doc_id):
    return get_db().execute(
        """
        SELECT documents.*, companies.name AS company_name
        FROM documents
        JOIN companies ON companies.id = documents.company_id
        WHERE documents.id = ?
        """,
        (doc_id,),
    ).fetchone()


def list_attachments(document_id):
    return get_db().execute(
        """
        SELECT *
        FROM attachments
        WHERE document_id = ?
        ORDER BY id
        """,
        (document_id,),
    ).fetchall()


def get_attachment(attachment_id):
    return get_db().execute(
        """
        SELECT *
        FROM attachments
        WHERE id = ?
        """,
        (attachment_id,),
    ).fetchone()


def get_share_link(code):
    return get_db().execute(
        """
        SELECT share_links.*, documents.reference, documents.company_id
        FROM share_links
        JOIN documents ON documents.id = share_links.document_id
        WHERE share_links.code = ? AND share_links.active = 1
        """,
        (code,),
    ).fetchone()


def attachment_path(attachment):
    return Path(current_app.config["STORAGE_DIR"]) / attachment["storage_name"]


def create_attachment(document_id, uploaded_by, file_storage):
    filename = os.path.basename(file_storage.filename or "memo.txt")
    storage_name = f"{uuid4().hex}-{filename}"
    target = Path(current_app.config["STORAGE_DIR"]) / storage_name
    file_storage.save(target)

    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO attachments
            (document_id, filename, content_type, storage_name, byte_length, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            filename,
            file_storage.mimetype or "application/octet-stream",
            storage_name,
            target.stat().st_size,
            uploaded_by,
        ),
    )
    db.commit()
    return cursor.lastrowid


def record_audit(user_id, action, document_id, attachment_id=None):
    db = get_db()
    db.execute(
        """
        INSERT INTO audit_events (user_id, action, document_id, attachment_id)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, action, document_id, attachment_id),
    )
    db.commit()

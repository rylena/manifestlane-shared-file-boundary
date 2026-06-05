from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for

from . import data_store as store
from .auth import login_required

bp = Blueprint("documents", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
    documents = store.list_documents_for_user(g.user)
    return render_template("dashboard.html", documents=documents)


@bp.route("/search")
@login_required
def search():
    query = request.args.get("q", "")
    documents = store.search_documents(g.user, query) if query else []
    return render_template("search.html", documents=documents, query=query)


@bp.route("/documents/<int:doc_id>")
@login_required
def detail(doc_id):
    document = store.get_document_for_user(g.user, doc_id)
    if document is None:
        abort(404)
    attachments = store.list_attachments(doc_id)
    return render_template("detail.html", document=document, attachments=attachments)


@bp.route("/documents/<int:doc_id>/attachments", methods=("POST",))
@login_required
def upload_attachment(doc_id):
    if not store.user_can_see_document(g.user, doc_id):
        abort(404)

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        flash("Choose a memo file to upload")
        return redirect(url_for("documents.detail", doc_id=doc_id))

    attachment_id = store.create_attachment(doc_id, g.user["id"], uploaded)
    store.record_audit(g.user["id"], "upload", doc_id, attachment_id)
    flash("Memo uploaded")
    return redirect(url_for("documents.detail", doc_id=doc_id))


@bp.route("/documents/<int:doc_id>/attachments/<int:attachment_id>")
@login_required
def download_attachment(doc_id, attachment_id):
    if not store.user_can_see_document(g.user, doc_id):
        abort(404)

    attachment = store.get_attachment(attachment_id)
    if attachment is None:
        abort(404)

    store.record_audit(g.user["id"], "download", doc_id, attachment_id)
    return _send_attachment(attachment)


@bp.route("/shares/<code>")
def shared_document(code):
    link = store.get_share_link(code)
    if link is None:
        abort(404)

    document = store.get_document(link["document_id"])
    if document is None:
        abort(404)

    attachments = store.list_attachments(document["id"])
    return render_template("share.html", code=code, document=document, attachments=attachments)


@bp.route("/shares/<code>/attachments/<int:attachment_id>")
def shared_attachment(code, attachment_id):
    link = store.get_share_link(code)
    if link is None:
        abort(404)

    attachment = store.get_attachment(attachment_id)
    if attachment is None:
        abort(404)

    store.record_audit(link["created_by"], "shared_download", link["document_id"], attachment_id)
    return _send_attachment(attachment)


def _send_attachment(attachment):
    path = store.attachment_path(attachment)
    return send_file(
        path,
        mimetype=attachment["content_type"],
        as_attachment=True,
        download_name=attachment["filename"],
    )

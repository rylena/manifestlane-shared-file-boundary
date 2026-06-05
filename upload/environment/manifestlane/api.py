from flask import Blueprint, abort, jsonify, request, send_file

from . import data_store as store

bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _bearer_token():
    header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not header.startswith(prefix):
        return None
    return header[len(prefix):].strip()


@bp.route("/documents")
def documents_index():
    token = _bearer_token()
    user = store.get_user_for_token(token)
    if user is None:
        abort(401)

    documents = store.list_documents_for_user(user)
    return jsonify(
        {
            "documents": [
                {
                    "id": row["id"],
                    "reference": row["reference"],
                    "vessel": row["vessel"],
                    "status": row["status"],
                    "destination": row["destination"],
                }
                for row in documents
            ]
        }
    )


@bp.route("/documents/<int:doc_id>/attachments/<int:attachment_id>")
def attachment_download(doc_id, attachment_id):
    token = _bearer_token()
    user = store.get_user_for_token(token)
    if user is None:
        abort(401)

    if not store.user_can_see_document(user, doc_id):
        abort(404)

    attachment = store.get_attachment(attachment_id)
    if attachment is None:
        abort(404)

    store.record_audit(user["id"], "api_download", doc_id, attachment_id)
    path = store.attachment_path(attachment)
    return send_file(
        path,
        mimetype=attachment["content_type"],
        as_attachment=True,
        download_name=attachment["filename"],
    )

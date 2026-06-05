import os
from pathlib import Path

from flask import Flask, redirect, url_for

from . import api, auth, documents
from .database import close_db, init_db


def create_app(testing=False):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("MANIFESTLANE_SECRET", "manifestlane-local-dev"),
        DATABASE=os.environ.get(
            "MANIFESTLANE_DB",
            str(Path(app.instance_path) / "manifestlane.sqlite"),
        ),
        STORAGE_DIR=os.environ.get(
            "MANIFESTLANE_STORAGE",
            str(Path(app.instance_path) / "files"),
        ),
        MAX_CONTENT_LENGTH=1024 * 1024,
        TESTING=testing,
    )

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["STORAGE_DIR"]).mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)
    app.register_blueprint(auth.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(api.bp)

    @app.route("/")
    def index():
        if auth.current_user() is None:
            return redirect(url_for("auth.login"))
        return redirect(url_for("documents.dashboard"))

    with app.app_context():
        init_db()

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080)

from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS

from app.config import Config
from app.extensions import db


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["ARCHIVE_DIR"]).mkdir(parents=True, exist_ok=True)

    from app.api import api_bp
    from app.ai.provider import AIProviderError
    from app.services.state_machine import FlowError

    app.register_blueprint(api_bp)

    @app.errorhandler(AIProviderError)
    def handle_ai_error(exc):
        return (
            jsonify({"code": "ai_error", "message": str(exc)}),
            getattr(exc, "status_code", 502),
        )

    @app.errorhandler(FlowError)
    def handle_flow_error(exc):
        return jsonify({"code": "invalid_transition", "message": str(exc)}), 409

    with app.app_context():
        from app import models  # noqa: F401  register models

        if app.config.get("AUTO_CREATE_TABLES", True):
            db.create_all()
            from app.schema import ensure_sqlite_columns

            ensure_sqlite_columns()

    @app.get("/")
    def index():
        return jsonify(
            {
                "service": "oversea-mvp",
                "version": "0.1.0",
                "docs": "/api/health",
            }
        )

    return app

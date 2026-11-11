from flask import jsonify
from sqlalchemy import text

from app.api import api_bp
from app.extensions import db


@api_bp.get("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return jsonify(
        {
            "status": "ok",
            "service": "oversea-mvp",
            "version": "0.1.0",
        }
    )

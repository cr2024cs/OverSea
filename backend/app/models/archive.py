from datetime import datetime

from app.extensions import db
from app.models.base import new_id


class Archive(db.Model):
    __tablename__ = "archives"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    manifest_json = db.Column(db.JSON, nullable=False, default=dict)
    zip_path = db.Column(db.String(500), nullable=False)
    file_hash = db.Column(db.String(128), nullable=False)
    retention_until = db.Column(db.Date, nullable=True)
    generated_by = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

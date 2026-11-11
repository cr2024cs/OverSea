from datetime import datetime

from app.extensions import db
from app.models.base import TimestampMixin, new_id


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="pm")
    provider_id = db.Column(
        db.String(32), db.ForeignKey("providers.id"), nullable=True, index=True
    )
    active = db.Column(db.Boolean, nullable=False, default=True)


class ConfigItem(TimestampMixin, db.Model):
    __tablename__ = "config_items"
    __table_args__ = (db.UniqueConstraint("type", "code", name="uq_config_type_code"),)

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    type = db.Column(db.String(40), nullable=False, index=True)
    code = db.Column(db.String(60), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    sort = db.Column(db.Integer, nullable=False, default=0)
    extra_json = db.Column(db.JSON, nullable=False, default=dict)


class AccessToken(TimestampMixin, db.Model):
    __tablename__ = "access_tokens"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    token = db.Column(db.String(200), unique=True, nullable=False, index=True)
    role_type = db.Column(db.String(20), nullable=False)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=True, index=True)
    subject_id = db.Column(db.String(64), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, nullable=False, default=False)
    last_ip = db.Column(db.String(64), nullable=True)
    last_access_at = db.Column(db.DateTime, nullable=True)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), nullable=True, index=True)
    actor_id = db.Column(db.String(32), nullable=True)
    actor_label = db.Column(db.String(120), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    object_type = db.Column(db.String(60), nullable=True)
    object_id = db.Column(db.String(64), nullable=True)
    detail_json = db.Column(db.JSON, nullable=False, default=dict)
    ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

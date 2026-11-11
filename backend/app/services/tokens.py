import hashlib
import secrets
from datetime import datetime, timedelta

from flask import current_app

from app.extensions import db
from app.models import AccessToken
from app.utils import client_ip

ROLE_TYPES = {"client", "provider", "expert"}


def _digest(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_access_token(project_id, role_type, subject_id=None, ttl_days=None):
    if role_type not in ROLE_TYPES:
        raise ValueError(f"unsupported role_type: {role_type}")

    ttl = current_app.config["TOKEN_TTL_DAYS"] if ttl_days is None else ttl_days
    raw_token = secrets.token_urlsafe(48)
    row = AccessToken(
        token=_digest(raw_token),
        role_type=role_type,
        project_id=project_id,
        subject_id=subject_id,
        expires_at=datetime.utcnow() + timedelta(days=ttl),
    )
    db.session.add(row)
    db.session.flush()
    return raw_token, row


def resolve_access_token(raw_token):
    if not raw_token:
        return None, "invalid"

    row = AccessToken.query.filter_by(token=_digest(raw_token)).first()
    if row is None:
        return None, "invalid"
    if row.revoked:
        return None, "revoked"
    if row.expires_at <= datetime.utcnow():
        return None, "expired"

    row.last_ip = client_ip()
    row.last_access_at = datetime.utcnow()
    db.session.commit()
    return row, None


def revoke_access_token(row):
    row.revoked = True
    return row

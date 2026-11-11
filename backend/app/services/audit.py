from flask import g

from app.extensions import db
from app.models import AuditLog
from app.utils import client_ip


def record_audit(
    action,
    object_type=None,
    object_id=None,
    detail=None,
    project_id=None,
    actor=None,
    actor_label=None,
):
    if actor is None:
        actor = getattr(g, "current_user", None)

    if actor_label is None:
        actor_label = getattr(actor, "name", None) or getattr(actor, "email", None)

    row = AuditLog(
        project_id=project_id,
        actor_id=getattr(actor, "id", None),
        actor_label=actor_label,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail_json=detail or {},
        ip=client_ip(),
    )
    db.session.add(row)
    return row

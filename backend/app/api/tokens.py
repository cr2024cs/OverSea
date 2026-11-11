from flask import jsonify, request

from app.api import api_bp
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import AccessToken, Project
from app.services.audit import record_audit
from app.services.tokens import ROLE_TYPES, issue_access_token, revoke_access_token


@api_bp.post("/access-tokens")
@roles_required("pm", "admin")
def create_access_token():
    data = request.get_json(silent=True) or {}
    project_id = str(data.get("project_id", "")).strip()
    role_type = str(data.get("role_type", "")).strip()
    subject_id = data.get("subject_id")

    if not project_id:
        return error("validation_error", "缺少 project_id", 400)
    if role_type not in ROLE_TYPES:
        return error(
            "validation_error",
            "role_type 必须是 client、provider 或 expert",
            400,
        )

    project = db.session.get(Project, project_id)
    if project is None:
        return error("not_found", "项目不存在", 404)

    ttl_days = data.get("ttl_days")
    if ttl_days is not None:
        try:
            ttl_days = int(ttl_days)
        except (TypeError, ValueError):
            return error("validation_error", "ttl_days 必须是整数", 400)
        if ttl_days <= 0:
            return error("validation_error", "ttl_days 必须大于 0", 400)

    raw_token, row = issue_access_token(
        project_id=project_id,
        role_type=role_type,
        subject_id=subject_id,
        ttl_days=ttl_days,
    )
    record_audit(
        "access_token_created",
        object_type="access_token",
        object_id=row.id,
        project_id=project_id,
        detail={"role_type": role_type, "subject_id": subject_id},
    )
    db.session.commit()

    return (
        jsonify(
            {
                "data": {
                    "id": row.id,
                    "token": raw_token,
                    "role_type": row.role_type,
                    "project_id": row.project_id,
                    "subject_id": row.subject_id,
                    "expires_at": row.expires_at.isoformat(),
                }
            }
        ),
        201,
    )


@api_bp.post("/access-tokens/<token_id>/revoke")
@roles_required("pm", "admin")
def revoke_token(token_id):
    row = db.session.get(AccessToken, token_id)
    if row is None:
        return error("not_found", "令牌不存在", 404)

    revoke_access_token(row)
    record_audit(
        "access_token_revoked",
        object_type="access_token",
        object_id=row.id,
        project_id=row.project_id,
    )
    db.session.commit()
    return jsonify({"data": {"id": row.id, "revoked": True}})

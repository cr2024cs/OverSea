from flask import jsonify

from app.api import api_bp
from app.api.errors import error
from app.api.projects import project_summary
from app.extensions import db
from app.models import Project
from app.services.permissions import ensure_project_scope
from app.services.tokens import resolve_access_token

TOKEN_ERRORS = {
    "invalid": ("invalid_access_token", "链接无效"),
    "revoked": ("access_token_revoked", "链接已作废"),
    "expired": ("access_token_expired", "链接已过期"),
}


def _resolve(raw_token):
    row, reason = resolve_access_token(raw_token)
    if row is None:
        code, message = TOKEN_ERRORS.get(reason, ("invalid_access_token", "链接无效"))
        return None, error(code, message, 401)
    return row, None


@api_bp.get("/link/<token>/whoami")
def link_whoami(token):
    row, failure = _resolve(token)
    if failure:
        return failure

    project = db.session.get(Project, row.project_id) if row.project_id else None
    return jsonify(
        {
            "data": {
                "role_type": row.role_type,
                "project_id": row.project_id,
                "project_name": project.name if project else None,
                "subject_id": row.subject_id,
                "expires_at": row.expires_at.isoformat(),
            }
        }
    )


@api_bp.get("/link/<token>/project")
def link_project(token):
    row, failure = _resolve(token)
    if failure:
        return failure

    project = db.session.get(Project, row.project_id) if row.project_id else None
    if project is None:
        return error("not_found", "项目不存在", 404)
    return jsonify({"data": project_summary(project)})


@api_bp.get("/link/<token>/projects/<project_id>")
def link_scoped_project(token, project_id):
    row, failure = _resolve(token)
    if failure:
        return failure

    try:
        ensure_project_scope(row, project_id)
    except PermissionError:
        return error("forbidden", "令牌无权访问该项目", 403)

    project = db.session.get(Project, project_id)
    if project is None:
        return error("not_found", "项目不存在", 404)
    return jsonify({"data": project_summary(project)})

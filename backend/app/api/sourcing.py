from flask import g, jsonify, request

from app.api import api_bp
from app.api.deps import login_required, roles_required
from app.api.errors import error
from app.extensions import db
from app.models import Candidate, Project, Provider, Task
from app.services.audit import record_audit
from app.services.permissions import can_access_project
from app.services.sourcing import (
    candidate_payload,
    candidates_payload,
    catalog_payload,
    generate_candidates,
    save_selection,
)
from app.services.tokens import resolve_access_token


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    if not can_access_project(g.current_user, project):
        return None, error("forbidden", "无权访问该项目", 403)
    return project, None


def _client_token(raw_token):
    row, reason = resolve_access_token(raw_token)
    if row is None:
        messages = {
            "invalid": ("invalid_access_token", "链接无效"),
            "revoked": ("access_token_revoked", "链接已作废"),
            "expired": ("access_token_expired", "链接已过期"),
        }
        code, message = messages.get(reason, ("invalid_access_token", "链接无效"))
        return None, error(code, message, 401)
    if row.role_type != "client":
        return None, error("forbidden", "该链接不是客户链接", 403)
    return row, None


@api_bp.get("/projects/<project_id>/service-catalog")
@login_required
def get_service_catalog(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    return jsonify({"data": catalog_payload(project)})


@api_bp.post("/projects/<project_id>/selection")
@login_required
def save_project_selection(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    codes = data.get("codes") or []
    if g.current_user.role == "client":
        payload = save_selection(project, codes, source="client")
        actor_label = f"client:{g.current_user.email}"
    else:
        override_reason = str(data.get("override_reason", "")).strip()
        if not override_reason:
            return error("validation_error", "PM 代选需填写原因", 400)
        payload = save_selection(
            project, codes, source="pm", override_reason=override_reason
        )
        actor_label = g.current_user.name
    record_audit(
        "selection_saved",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        actor_label=actor_label,
        detail={
            "codes": payload["selection"]["codes"],
            "source": payload["selection"]["source"],
        },
    )
    db.session.commit()
    return jsonify({"data": payload})


@api_bp.get("/link/<token>/selection")
def get_link_selection(token):
    row, failure = _client_token(token)
    if failure:
        return failure
    project = db.session.get(Project, row.project_id)
    if project is None:
        return error("not_found", "项目不存在", 404)
    return jsonify({"data": catalog_payload(project)})


@api_bp.post("/link/<token>/selection")
def save_link_selection(token):
    row, failure = _client_token(token)
    if failure:
        return failure
    project = db.session.get(Project, row.project_id)
    if project is None:
        return error("not_found", "项目不存在", 404)

    data = request.get_json(silent=True) or {}
    codes = data.get("codes") or []
    payload = save_selection(project, codes, source="client")
    record_audit(
        "selection_saved",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        actor_label=f"client:{row.subject_id or row.id}",
        detail={"codes": payload["selection"]["codes"], "source": "client"},
    )
    db.session.commit()
    return jsonify({"data": payload})


@api_bp.get("/projects/<project_id>/candidates")
@login_required
def list_candidates(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    return jsonify({"data": candidates_payload(project)})


@api_bp.post("/projects/<project_id>/candidates/generate")
@roles_required("pm", "admin")
def generate_project_candidates(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    task_codes = data.get("task_codes") or None
    try:
        payload = generate_candidates(project, task_codes=task_codes)
    except ValueError as exc:
        return error("validation_error", str(exc), 400)

    record_audit(
        "candidates_generated",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        detail={"tasks": [item["task_code"] for item in payload]},
    )
    db.session.commit()
    return jsonify({"data": payload})


@api_bp.post("/projects/<project_id>/candidates")
@roles_required("pm", "admin")
def add_candidate(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    task_code = str(data.get("task_code", "")).strip()
    provider_id = str(data.get("provider_id", "")).strip()
    reason = str(data.get("reason", "")).strip() or "PM 手工添加"

    task = Task.query.filter_by(project_id=project.id, code=task_code).first()
    if task is None:
        return error("not_found", "任务不存在", 404)
    provider = db.session.get(Provider, provider_id)
    if provider is None:
        return error("not_found", "服务商不存在", 404)

    candidate = Candidate.query.filter_by(
        task_id=task.id, provider_id=provider.id
    ).first()
    if candidate is None:
        candidate = Candidate(
            project_id=project.id,
            task_id=task.id,
            provider_id=provider.id,
        )
        db.session.add(candidate)
    candidate.match_score = 0
    candidate.reason = reason
    candidate.source_type = provider.source_type
    candidate.evidence_json = {
        "qualification": provider.qualification,
        "city": provider.city,
        "evidence_level": provider.evidence_level,
    }
    candidate.status = "shortlisted"
    candidate.reject_reason = None
    db.session.commit()
    return jsonify({"data": candidate_payload(candidate, provider, task)}), 201


@api_bp.post("/candidates/<candidate_id>/reject")
@roles_required("pm", "admin")
def reject_candidate(candidate_id):
    candidate = db.session.get(Candidate, candidate_id)
    if candidate is None:
        return error("not_found", "候选不存在", 404)

    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason", "")).strip()
    if not reason:
        return error("validation_error", "请填写不合适原因", 400)

    candidate.status = "rejected"
    candidate.reject_reason = reason[:255]
    record_audit(
        "candidate_rejected",
        object_type="candidate",
        object_id=candidate.id,
        project_id=candidate.project_id,
        detail={"reason": reason},
    )
    db.session.commit()
    return jsonify({"data": {"id": candidate.id, "status": candidate.status}})


@api_bp.get("/providers")
@roles_required("pm", "admin")
def list_providers():
    rows = Provider.query.order_by(Provider.name.asc()).all()
    return jsonify(
        {
            "data": [
                {
                    "id": row.id,
                    "name": row.name,
                    "type": row.type,
                    "city": row.city,
                    "evidence_level": row.evidence_level,
                    "source_type": row.source_type,
                }
                for row in rows
            ]
        }
    )

from datetime import datetime

from flask import g, jsonify, request

from app.api import api_bp
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import Milestone, PerformanceEvent, Project, Provider, Task, User
from app.services.audit import record_audit
from app.services.state_machine import fire_milestone
from app.services.tokens import issue_access_token, resolve_access_token

WEIGHTS = {
    "completeness": 0.30,
    "quality": 0.40,
    "executability": 0.20,
    "timeliness": 0.10,
}


def _resolve_expert(raw_token, milestone_id=None):
    row, reason = resolve_access_token(raw_token)
    if row is None:
        messages = {
            "invalid": ("invalid_access_token", "链接无效"),
            "revoked": ("access_token_revoked", "链接已作废"),
            "expired": ("access_token_expired", "链接已过期"),
        }
        code, message = messages.get(reason, ("invalid_access_token", "链接无效"))
        return None, None, error(code, message, 401)
    if row.role_type != "expert":
        return None, None, error("forbidden", "该链接不是专家评审链接", 403)
    milestone = db.session.get(Milestone, row.subject_id)
    if milestone is None:
        return None, None, error("not_found", "评审节点不存在", 404)
    if milestone_id and milestone.id != milestone_id:
        return None, None, error("forbidden", "令牌与节点不匹配", 403)
    return row, milestone, None


@api_bp.post("/milestones/<milestone_id>/expert-invite")
@roles_required("pm", "admin")
def invite_expert(milestone_id):
    milestone = db.session.get(Milestone, milestone_id)
    if milestone is None:
        return error("not_found", "节点不存在", 404)
    if milestone.status not in {"expert_review", "client_confirm"}:
        return error("conflict", "请先完成 PM 初审", 409)

    data = request.get_json(silent=True) or {}
    email = str(data.get("expert_email") or "expert@demo.local").strip().lower()
    expert = User.query.filter_by(email=email, role="expert", active=True).first()
    if expert is None:
        return error("not_found", "专家账号不存在", 404)
    milestone.expert_user_id = expert.id

    raw_token, row = issue_access_token(
        project_id=milestone.project_id,
        role_type="expert",
        subject_id=milestone.id,
    )
    record_audit(
        "expert_invited",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        detail={"expert_email": email},
    )
    db.session.commit()
    return (
        jsonify(
            {
                "data": {
                    "token": raw_token,
                    "expires_at": row.expires_at.isoformat(),
                    "link": f"/expert-link/{raw_token}",
                    "expert_email": email,
                }
            }
        ),
        201,
    )


@api_bp.get("/link/<token>/expert")
def expert_view(token):
    _row, milestone, failure = _resolve_expert(token)
    if failure:
        return failure

    task = db.session.get(Task, milestone.task_id) if milestone.task_id else None
    project = db.session.get(Project, milestone.project_id)
    return jsonify(
        {
            "data": {
                "milestone_id": milestone.id,
                "name": milestone.name,
                "task_code": task.code if task else None,
                "task_name": task.name if task else milestone.name,
                "project_name": project.name if project else None,
                "deliverable": milestone.deliverable,
                "acceptance_criteria": milestone.acceptance_criteria,
                "due_date": milestone.due_date.isoformat() if milestone.due_date else None,
                "submission_note": milestone.submission_note,
                "submission_files": milestone.submission_files_json or [],
                "rounds": milestone.rounds,
                "weights": WEIGHTS,
                "locked": milestone.expert_locked,
            }
        }
    )


@api_bp.post("/link/<token>/expert/review")
def submit_expert_review(token):
    _row, milestone, failure = _resolve_expert(token)
    if failure:
        return failure
    if milestone.expert_locked:
        return error("conflict", "评分已提交并锁定，不可修改", 409)

    data = request.get_json(silent=True) or {}
    scores = data.get("scores") or {}
    comment = str(data.get("comment", "")).strip()
    if not data.get("conflict_declared"):
        return error("validation_error", "请先声明无利益冲突", 400)
    if not comment:
        return error("validation_error", "请填写评审意见", 400)

    cleaned = {}
    for key in WEIGHTS:
        try:
            value = float(scores.get(key))
        except (TypeError, ValueError):
            return error("validation_error", f"{key} 必须是数字", 400)
        if value < 0 or value > 100:
            return error("validation_error", f"{key} 必须在 0 到 100 之间", 400)
        cleaned[key] = value

    total = round(sum(cleaned[key] * WEIGHTS[key] for key in WEIGHTS), 2)
    milestone.expert_scores_json = cleaned
    milestone.expert_total = total
    milestone.expert_comment = comment
    milestone.expert_submitted_at = datetime.utcnow()
    milestone.expert_locked = True
    fire_milestone(milestone, "expert_submitted")
    record_audit(
        "expert_review_submitted",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        detail={"total": total},
    )
    db.session.commit()
    return jsonify({"data": {"total": total, "locked": True}})


@api_bp.get("/providers/<provider_id>/events")
@roles_required("pm", "admin", "lawyer")
def provider_events(provider_id):
    provider = db.session.get(Provider, provider_id)
    if provider is None:
        return error("not_found", "服务商不存在", 404)
    rows = (
        PerformanceEvent.query.filter_by(provider_id=provider.id)
        .order_by(PerformanceEvent.occurred_at.desc())
        .all()
    )
    return jsonify(
        {
            "data": [
                {
                    "id": row.id,
                    "type": row.type,
                    "dimension": row.dimension,
                    "value": row.value,
                    "note": row.note,
                    "occurred_at": row.occurred_at.isoformat(),
                }
                for row in rows
            ]
        }
    )


@api_bp.get("/providers/<provider_id>/score")
@roles_required("pm", "admin", "lawyer")
def provider_score(provider_id):
    provider = db.session.get(Provider, provider_id)
    if provider is None:
        return error("not_found", "服务商不存在", 404)

    events = PerformanceEvent.query.filter_by(provider_id=provider.id).all()
    milestones = Milestone.query.filter_by(provider_id=provider.id).all()
    expert_totals = [
        row.expert_total for row in milestones if row.expert_total is not None
    ]
    finalized = [
        row for row in milestones if row.status in {"passed", "conditional", "failed"}
    ]
    passed = [row for row in finalized if row.status in {"passed", "conditional"}]

    dimensions = {
        "capability": round(sum(expert_totals) / len(expert_totals), 2)
        if expert_totals
        else None,
        "capacity": 100 if any(event.type == "quote_submitted" for event in events) else None,
        "quality": round(sum(expert_totals) / len(expert_totals), 2)
        if expert_totals
        else None,
        "delivery": round(len(passed) / len(finalized) * 100, 2) if finalized else None,
    }
    available = [value for value in dimensions.values() if value is not None]
    total = round(sum(available) / len(available), 2) if available else None
    return jsonify(
        {
            "data": {
                "provider_id": provider.id,
                "provider_name": provider.name,
                "dimensions": dimensions,
                "total": total,
                "data_sufficient": bool(available),
                "events": len(events),
                "milestones": len(milestones),
            }
        }
    )


def _expert_task_payload(milestone):
    task = db.session.get(Task, milestone.task_id) if milestone.task_id else None
    project = db.session.get(Project, milestone.project_id)
    return {
        "milestone_id": milestone.id,
        "name": milestone.name,
        "task_code": task.code if task else None,
        "task_name": task.name if task else milestone.name,
        "project_name": project.name if project else None,
        "deliverable": milestone.deliverable,
        "acceptance_criteria": milestone.acceptance_criteria,
        "due_date": milestone.due_date.isoformat() if milestone.due_date else None,
        "submission_note": milestone.submission_note,
        "submission_files": milestone.submission_files_json or [],
        "rounds": milestone.rounds,
        "weights": WEIGHTS,
        "locked": milestone.expert_locked,
        "status": milestone.status,
        "expert_total": milestone.expert_total,
    }


@api_bp.get("/expert/workbench")
@roles_required("expert")
def expert_workbench():
    rows = (
        Milestone.query.filter_by(expert_user_id=g.current_user.id)
        .order_by(Milestone.due_date.asc())
        .all()
    )
    return jsonify({"data": [_expert_task_payload(row) for row in rows]})


@api_bp.get("/expert/milestones/<milestone_id>")
@roles_required("expert")
def expert_milestone(milestone_id):
    milestone = db.session.get(Milestone, milestone_id)
    if milestone is None or milestone.expert_user_id != g.current_user.id:
        return error("not_found", "评审任务不存在", 404)
    return jsonify({"data": _expert_task_payload(milestone)})


@api_bp.post("/expert/milestones/<milestone_id>/review")
@roles_required("expert")
def expert_submit_review(milestone_id):
    milestone = db.session.get(Milestone, milestone_id)
    if milestone is None or milestone.expert_user_id != g.current_user.id:
        return error("not_found", "评审任务不存在", 404)
    if milestone.expert_locked:
        return error("conflict", "评分已提交并锁定，不可修改", 409)

    data = request.get_json(silent=True) or {}
    scores = data.get("scores") or {}
    comment = str(data.get("comment", "")).strip()
    if not data.get("conflict_declared"):
        return error("validation_error", "请先声明无利益冲突", 400)
    if not comment:
        return error("validation_error", "请填写评审意见", 400)

    cleaned = {}
    for key in WEIGHTS:
        try:
            value = float(scores.get(key))
        except (TypeError, ValueError):
            return error("validation_error", f"{key} 必须是数字", 400)
        if value < 0 or value > 100:
            return error("validation_error", f"{key} 必须在 0 到 100 之间", 400)
        cleaned[key] = value

    total = round(sum(cleaned[key] * WEIGHTS[key] for key in WEIGHTS), 2)
    milestone.expert_scores_json = cleaned
    milestone.expert_total = total
    milestone.expert_comment = comment
    milestone.expert_submitted_at = datetime.utcnow()
    milestone.expert_locked = True
    fire_milestone(milestone, "expert_submitted")
    record_audit(
        "expert_review_submitted",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        actor_label=f"expert:{g.current_user.email}",
        detail={"total": total},
    )
    db.session.commit()
    return jsonify({"data": {"total": total, "locked": True}})

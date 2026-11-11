from datetime import date, datetime

from flask import g, jsonify, request

from app.ai.provider import AIProvider
from app.api import api_bp
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import Milestone, PerformanceEvent, Project, Provider, Task
from app.services.audit import record_audit
from app.services.permissions import can_access_project
from app.services.review import normalize_findings
from app.services.state_machine import fire_milestone
from app.services.task_graph import compute_schedule
from app.services.tokens import resolve_access_token
from app.utils import client_ip


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    if not can_access_project(g.current_user, project):
        return None, error("forbidden", "无权访问该项目", 403)
    return project, None


def _milestone(milestone_id):
    milestone = db.session.get(Milestone, milestone_id)
    if milestone is None:
        return None, error("not_found", "节点不存在", 404)
    return milestone, None


def _provider_token(raw_token):
    token_row, reason = resolve_access_token(raw_token)
    if token_row is None:
        messages = {
            "invalid": ("invalid_access_token", "链接无效"),
            "revoked": ("access_token_revoked", "链接已作废"),
            "expired": ("access_token_expired", "链接已过期"),
        }
        code, message = messages.get(reason, ("invalid_access_token", "链接无效"))
        return None, error(code, message, 401)
    if token_row.role_type != "provider":
        return None, error("forbidden", "该链接不是服务商链接", 403)
    return token_row, None


def _milestone_payload(row):
    task = db.session.get(Task, row.task_id) if row.task_id else None
    provider = db.session.get(Provider, row.provider_id) if row.provider_id else None
    today = date.today()
    overdue_days = 0
    reminder_level = 0
    if row.due_date:
        delta = (row.due_date - today).days
        if delta < 0:
            overdue_days = -delta
            reminder_level = 7 if overdue_days >= 7 else 3 if overdue_days >= 3 else 1
        elif delta <= 1:
            reminder_level = 1
        elif delta <= 3:
            reminder_level = 3
        elif delta <= 7:
            reminder_level = 7

    return {
        "id": row.id,
        "task_code": task.code if task else None,
        "task_name": task.name if task else row.name,
        "name": row.name,
        "status": row.status,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "overdue_days": overdue_days,
        "reminder_level": reminder_level,
        "provider_id": row.provider_id,
        "provider_name": provider.name if provider else None,
        "acceptor_type": row.acceptor_type,
        "grace_days": row.grace_days,
        "rounds": row.rounds,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "submission_note": row.submission_note,
        "pm_review_status": row.pm_review_status,
        "expert_total": row.expert_total,
        "expert_locked": row.expert_locked,
        "client_confirmed_at": row.client_confirmed_at.isoformat()
        if row.client_confirmed_at
        else None,
    }


@api_bp.get("/projects/<project_id>/board")
@roles_required("pm", "admin", "lawyer", "client")
def project_board(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    milestones = (
        Milestone.query.filter_by(project_id=project.id)
        .order_by(Milestone.due_date.asc())
        .all()
    )
    counts = {}
    for row in milestones:
        counts[row.status] = counts.get(row.status, 0) + 1

    tasks = Task.query.filter_by(project_id=project.id).all()
    task_dicts = [
        {
            "code": task.code,
            "name": task.name,
            "duration_days": task.duration_days,
            "predecessors": task.predecessor_codes_json or [],
        }
        for task in tasks
    ]
    try:
        critical_path = compute_schedule(task_dicts)["critical_path"] if task_dicts else []
    except ValueError:
        critical_path = []

    return jsonify(
        {
            "data": {
                "summary": counts,
                "total": len(milestones),
                "critical_path": critical_path,
                "milestones": [_milestone_payload(row) for row in milestones],
            }
        }
    )


def _save_submission(milestone, note, files):
    milestone.submission_note = note
    milestone.submission_files_json = files or []
    milestone.submitted_at = datetime.utcnow()
    fire_milestone(milestone, "submit")
    milestone.pm_review_status = "pending"
    milestone.pm_review_note = None


@api_bp.post("/milestones/<milestone_id>/submission")
@roles_required("pm", "admin")
def submit_milestone(milestone_id):
    milestone, failure = _milestone(milestone_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    _save_submission(
        milestone,
        str(data.get("note", "")).strip(),
        data.get("files") or [],
    )
    record_audit(
        "milestone_submitted",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        detail={"source": "pm"},
    )
    db.session.commit()
    return jsonify({"data": _milestone_payload(milestone)})


@api_bp.post("/link/<token>/milestone/<milestone_id>/submission")
def submit_milestone_link(token, milestone_id):
    token_row, failure = _provider_token(token)
    if failure:
        return failure
    milestone, failure = _milestone(milestone_id)
    if failure:
        return failure
    if milestone.project_id != token_row.project_id:
        return error("forbidden", "链接与节点不属于同一项目", 403)
    if not token_row.subject_id or milestone.provider_id != token_row.subject_id:
        return error("forbidden", "令牌未绑定到该节点服务商", 403)

    data = request.get_json(silent=True) or {}
    _save_submission(
        milestone,
        str(data.get("note", "")).strip(),
        data.get("files") or [],
    )
    record_audit(
        "milestone_submitted",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        actor_label=f"provider:{token_row.subject_id}",
        detail={"source": "provider"},
    )
    db.session.commit()
    return jsonify({"data": _milestone_payload(milestone)})


@api_bp.post("/milestones/<milestone_id>/pm-review")
@roles_required("pm", "admin")
def pm_review_milestone(milestone_id):
    milestone, failure = _milestone(milestone_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    note = str(data.get("note", "")).strip()
    if decision not in {"accept", "return"}:
        return error("validation_error", "decision 必须是 accept 或 return", 400)
    if decision == "return" and not note:
        return error("validation_error", "退回需填写原因", 400)

    milestone.pm_review_status = "accepted" if decision == "accept" else "returned"
    milestone.pm_review_note = note or None
    if decision == "accept":
        fire_milestone(milestone, "pm_accept")
    else:
        fire_milestone(milestone, "pm_return")

    record_audit(
        "milestone_pm_reviewed",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        detail={"decision": decision},
    )
    db.session.commit()
    return jsonify({"data": _milestone_payload(milestone)})


@api_bp.post("/milestones/<milestone_id>/review")
@roles_required("pm", "admin", "lawyer")
def review_milestone_answer(milestone_id):
    milestone, failure = _milestone(milestone_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    source_text = str(data.get("text") or milestone.submission_note or "").strip()
    if not source_text:
        return error("validation_error", "请提供服务商答复或交付物文本", 400)

    from app.models import Finding

    Finding.query.filter_by(milestone_id=milestone.id).delete(synchronize_session=False)

    provider = AIProvider()
    outcome = provider.run(
        "review_answer",
        {
            "project_id": milestone.project_id,
            "milestone_id": milestone.id,
            "text": source_text[:8000],
        },
    )
    raw = outcome["result"].get("findings", [])
    normalized = normalize_findings(raw, source_text)

    findings = []
    for item in normalized:
        row = Finding(
            project_id=milestone.project_id,
            milestone_id=milestone.id,
            **item,
        )
        db.session.add(row)
        findings.append(row)
    fire_milestone(milestone, "review")

    record_audit(
        "ai_call",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        detail={
            "step": "review_answer",
            "model": outcome["model"],
            "findings": len(findings),
        },
    )
    db.session.commit()
    return jsonify({"data": [_finding_payload(row) for row in findings]})


def _finding_payload(row):
    return {
        "id": row.id,
        "milestone_id": row.milestone_id,
        "category": row.category,
        "severity": row.severity,
        "conclusion_level": row.conclusion_level,
        "quote_text": row.quote_text,
        "reason": row.reason,
        "question_zh": row.question_zh,
        "question_en": row.question_en,
        "is_legal": row.is_legal,
        "sources": row.sources_json,
        "citation_status": row.citation_status,
        "reviewer_status": row.reviewer_status,
        "reply_text": row.reply_text,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def _unlock_dependents(project_id, completed_task):
    if completed_task is None:
        return []
    tasks = Task.query.filter_by(project_id=project_id).all()
    by_code = {task.code: task for task in tasks}
    unlocked = []
    for task in tasks:
        if completed_task.code not in (task.predecessor_codes_json or []):
            continue
        predecessors = [
            by_code.get(code) for code in (task.predecessor_codes_json or [])
        ]
        if all(row is not None and row.status == "completed" for row in predecessors):
            task.locked = False
            unlocked.append(task.code)
    return unlocked


@api_bp.post("/milestones/<milestone_id>/finalize")
@roles_required("pm", "admin")
def finalize_milestone(milestone_id):
    milestone, failure = _milestone(milestone_id)
    if failure:
        return failure
    if not milestone.expert_locked:
        return error("conflict", "专家评分尚未提交并锁定", 409)

    total = milestone.expert_total or 0
    if total >= 85:
        conclusion = "passed"
    elif total >= 70:
        conclusion = "conditional"
    else:
        conclusion = "failed"

    fire_milestone(milestone, "finalize", conclusion=conclusion)
    unlocked = []
    if conclusion == "failed":
        milestone.rounds = (milestone.rounds or 0) + 1
    else:
        task = (
            db.session.get(Task, milestone.task_id) if milestone.task_id else None
        )
        if task is not None:
            task.status = "completed"
        unlocked = _unlock_dependents(milestone.project_id, task)

    if milestone.provider_id:
        db.session.add(
            PerformanceEvent(
                project_id=milestone.project_id,
                provider_id=milestone.provider_id,
                milestone_id=milestone.id,
                type=f"milestone_{conclusion}",
                dimension="delivery",
                value=total,
                note=f"节点 {milestone.name} 验收结论 {conclusion}",
            )
        )

    record_audit(
        "milestone_finalized",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        detail={"conclusion": conclusion, "total": total, "unlocked": unlocked},
    )
    db.session.commit()
    payload = _milestone_payload(milestone)
    payload["unlocked_tasks"] = unlocked
    return jsonify({"data": payload})


@api_bp.post("/milestones/<milestone_id>/rectify")
@roles_required("pm", "admin")
def rectify_milestone(milestone_id):
    milestone, failure = _milestone(milestone_id)
    if failure:
        return failure
    fire_milestone(milestone, "rectify")
    milestone.expert_locked = False
    milestone.expert_submitted_at = None
    milestone.expert_scores_json = {}
    milestone.expert_total = None
    milestone.expert_comment = None
    record_audit(
        "milestone_rectification",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
    )
    db.session.commit()
    return jsonify({"data": _milestone_payload(milestone)})


@api_bp.post("/milestones/<milestone_id>/client-confirm")
@roles_required("pm", "admin")
def client_confirm_milestone(milestone_id):
    milestone, failure = _milestone(milestone_id)
    if failure:
        return failure
    if milestone.client_confirmed_at is None:
        milestone.client_confirmed_at = datetime.utcnow()
        milestone.client_confirm_ip = client_ip()
        record_audit(
            "milestone_client_confirmed",
            object_type="milestone",
            object_id=milestone.id,
            project_id=milestone.project_id,
        )
        db.session.commit()
    return jsonify({"data": _milestone_payload(milestone)})


@api_bp.post("/milestones/<milestone_id>/reminder-draft")
@roles_required("pm", "admin")
def reminder_draft(milestone_id):
    milestone, failure = _milestone(milestone_id)
    if failure:
        return failure
    task = db.session.get(Task, milestone.task_id) if milestone.task_id else None
    name = task.name if task else milestone.name
    due = milestone.due_date.isoformat() if milestone.due_date else "待定"
    text = (
        f"Dear provider, this is a reminder that the deliverable for "
        f"'{name}' is due on {due}. Please submit the deliverable or provide a status update."
    )
    client_text = (
        f"【进度提醒】节点“{name}”计划于 {due} 交付，"
        "平台正在跟进服务商提交，如有阻塞会及时同步。"
    )
    return jsonify({"data": {"provider_en": text, "client_zh": client_text}})

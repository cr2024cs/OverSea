from datetime import datetime

from flask import g, jsonify, request

from app.api import api_bp
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import Finding, Milestone, Project, QueryLetter, RFP
from app.services.audit import record_audit
from app.services.state_machine import fire_query_letter
from app.services.tokens import resolve_access_token


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    return project, None


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


def finding_payload(row):
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


def letter_payload(row, include_findings=True):
    payload = {
        "id": row.id,
        "project_id": row.project_id,
        "provider_id": row.provider_id,
        "content": row.content,
        "approval_status": row.approval_status,
        "approved_by_role": row.approved_by_role,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "status": row.status,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "created_at": row.created_at.isoformat(),
    }
    if include_findings:
        ids = row.finding_ids_json or []
        rows = Finding.query.filter(Finding.id.in_(ids)).all() if ids else []
        payload["findings"] = [finding_payload(item) for item in rows]
    return payload


@api_bp.get("/projects/<project_id>/query-letters")
@roles_required("pm", "admin", "lawyer")
def list_query_letters(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    rows = (
        QueryLetter.query.filter_by(project_id=project.id)
        .order_by(QueryLetter.created_at.desc())
        .all()
    )
    return jsonify({"data": [letter_payload(row) for row in rows]})


@api_bp.post("/projects/<project_id>/query-letters")
@roles_required("pm", "admin")
def create_query_letter(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    milestone_id = data.get("milestone_id")
    query = Finding.query.filter_by(project_id=project.id)
    if milestone_id:
        query = query.filter_by(milestone_id=milestone_id)

    used_ids = set()
    for letter in QueryLetter.query.filter_by(project_id=project.id).all():
        used_ids.update(letter.finding_ids_json or [])

    findings = [
        row
        for row in query.order_by(Finding.created_at.asc()).all()
        if row.id not in used_ids
        and row.citation_status == "verified"
        and row.reviewer_status != "rejected"
        and row.closed_at is None
    ]
    if not findings:
        return error("validation_error", "没有可进入质询函的发现", 400)

    provider_id = data.get("provider_id")
    if not provider_id:
        milestone = db.session.get(Milestone, milestone_id) if milestone_id else None
        if milestone is not None:
            provider_id = milestone.provider_id
    if not provider_id:
        first_milestone = Milestone.query.filter_by(project_id=project.id).first()
        if first_milestone is not None:
            provider_id = first_milestone.provider_id
    if not provider_id:
        first_rfp = RFP.query.filter_by(project_id=project.id).first()
        if first_rfp is not None:
            provider_id = first_rfp.provider_id
    if not provider_id:
        return error("validation_error", "无法确定质询对象服务商", 400)

    lines = ["质询函", "", f"项目：{project.name}", "客户名称：已隐去", ""]
    for index, finding in enumerate(findings, start=1):
        lines.append(f"{index}. [{finding.category}] {finding.question_zh or ''}")
        lines.append(f"   原文：{finding.quote_text or ''}")
        lines.append("")
    content = "\n".join(lines)

    row = QueryLetter(
        project_id=project.id,
        provider_id=provider_id,
        finding_ids_json=[finding.id for finding in findings],
        content=content,
        approval_status="pending",
        status="draft",
    )
    db.session.add(row)
    record_audit(
        "query_letter_created",
        object_type="query_letter",
        object_id=row.id,
        project_id=project.id,
        detail={"findings": len(findings)},
    )
    db.session.commit()
    return jsonify({"data": letter_payload(row)}), 201


@api_bp.post("/query-letters/<letter_id>/approve")
@roles_required("lawyer")
def approve_query_letter(letter_id):
    row = db.session.get(QueryLetter, letter_id)
    if row is None:
        return error("not_found", "质询函不存在", 404)
    if row.approval_status == "approved":
        return jsonify({"data": letter_payload(row)})
    if row.approval_status == "rejected":
        return error("conflict", "已驳回的质询函不能批准", 409)

    row.approval_status = "approved"
    row.approved_by = g.current_user.id
    row.approved_by_role = g.current_user.role
    row.approved_at = datetime.utcnow()
    record_audit(
        "query_letter_approved",
        object_type="query_letter",
        object_id=row.id,
        project_id=row.project_id,
    )
    db.session.commit()
    return jsonify({"data": letter_payload(row)})


@api_bp.post("/query-letters/<letter_id>/reject")
@roles_required("lawyer")
def reject_query_letter(letter_id):
    row = db.session.get(QueryLetter, letter_id)
    if row is None:
        return error("not_found", "质询函不存在", 404)

    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason", "")).strip()
    if not reason:
        return error("validation_error", "驳回需填写原因（如“误报”）", 400)

    row.approval_status = "rejected"
    row.approved_by = g.current_user.id
    row.approved_by_role = g.current_user.role
    row.approved_at = datetime.utcnow()
    finding_ids = row.finding_ids_json or []
    for finding in Finding.query.filter(Finding.id.in_(finding_ids)).all():
        finding.reviewer_status = "rejected"
        finding.reject_reason = reason[:255]
        finding.reviewed_at = datetime.utcnow()
    record_audit(
        "query_letter_rejected",
        object_type="query_letter",
        object_id=row.id,
        project_id=row.project_id,
        detail={"reason": reason},
    )
    db.session.commit()
    return jsonify({"data": letter_payload(row)})


@api_bp.post("/query-letters/<letter_id>/send")
@roles_required("pm", "admin", "lawyer")
def send_query_letter(letter_id):
    row = db.session.get(QueryLetter, letter_id)
    if row is None:
        return error("not_found", "质询函不存在", 404)
    if row.status != "draft":
        return error("conflict", "当前状态不能发送", 409)
    if row.approval_status != "approved":
        return error("forbidden", "法律类质询未经复核律师批准", 403)
    if row.approved_by_role != "lawyer":
        return error("forbidden", "审批人不是复核律师", 403)

    ids = row.finding_ids_json or []
    findings = Finding.query.filter(Finding.id.in_(ids)).all() if ids else []
    if any(finding.citation_status != "verified" for finding in findings):
        return error("validation_error", "存在无法核对的引用，不能发送", 400)

    fire_query_letter(row, "send")
    row.sent_at = datetime.utcnow()
    record_audit(
        "query_letter_sent",
        object_type="query_letter",
        object_id=row.id,
        project_id=row.project_id,
    )
    db.session.commit()
    return jsonify({"data": letter_payload(row)})


@api_bp.get("/link/<token>/query-letter")
def link_query_letter(token):
    token_row, failure = _provider_token(token)
    if failure:
        return failure
    row = (
        QueryLetter.query.filter_by(
            project_id=token_row.project_id,
            provider_id=token_row.subject_id,
        )
        .filter(QueryLetter.status.in_(["sent", "replied"]))
        .order_by(QueryLetter.sent_at.desc())
        .first()
    )
    if row is None:
        return error("not_found", "暂无待回复质询函", 404)
    return jsonify({"data": letter_payload(row)})


@api_bp.post("/link/<token>/query-letter/reply")
def reply_query_letter(token):
    token_row, failure = _provider_token(token)
    if failure:
        return failure
    row = (
        QueryLetter.query.filter_by(
            project_id=token_row.project_id,
            provider_id=token_row.subject_id,
        )
        .filter(QueryLetter.status.in_(["sent", "replied"]))
        .order_by(QueryLetter.sent_at.desc())
        .first()
    )
    if row is None:
        return error("not_found", "暂无待回复质询函", 404)

    data = request.get_json(silent=True) or {}
    replies = data.get("replies") or []
    if not replies:
        return error("validation_error", "replies 不能为空", 400)

    ids = set(row.finding_ids_json or [])
    for item in replies:
        finding_id = item.get("finding_id")
        if finding_id not in ids:
            continue
        finding = db.session.get(Finding, finding_id)
        if finding is None:
            continue
        finding.reply_text = str(item.get("reply", "")).strip()
        finding.reviewer_status = "replied"

    findings = Finding.query.filter(Finding.id.in_(ids)).all() if ids else []
    if findings and all(finding.reply_text for finding in findings):
        fire_query_letter(row, "reply")
    record_audit(
        "query_letter_replied",
        object_type="query_letter",
        object_id=row.id,
        project_id=row.project_id,
        actor_label=f"provider:{token_row.subject_id}",
    )
    db.session.commit()
    return jsonify({"data": letter_payload(row)})


@api_bp.post("/query-letters/<letter_id>/close")
@roles_required("pm", "admin")
def close_query_letter(letter_id):
    row = db.session.get(QueryLetter, letter_id)
    if row is None:
        return error("not_found", "质询函不存在", 404)

    ids = row.finding_ids_json or []
    findings = Finding.query.filter(Finding.id.in_(ids)).all() if ids else []
    if any(not finding.reply_text for finding in findings):
        return error("validation_error", "仍有发现未回复", 400)

    now = datetime.utcnow()
    for finding in findings:
        finding.closed_at = now
        finding.reviewer_status = "closed"
    fire_query_letter(row, "close")
    row.closed_at = now
    record_audit(
        "query_letter_closed",
        object_type="query_letter",
        object_id=row.id,
        project_id=row.project_id,
    )
    db.session.commit()
    return jsonify({"data": letter_payload(row)})

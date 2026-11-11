from datetime import datetime

from flask import g, jsonify, request

from app.api import api_bp
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import Project, Proposal
from app.services.audit import record_audit
from app.services.proposal import build_proposal_content
from app.services.state_machine import fire_project, fire_proposal
from app.services.tokens import resolve_access_token
from app.utils import client_ip

ROLE_TYPES = {"client"}


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    return project, None


def _latest(project_id):
    return (
        Proposal.query.filter_by(project_id=project_id)
        .order_by(Proposal.version.desc())
        .first()
    )


def proposal_payload(row):
    return {
        "id": row.id,
        "version": row.version,
        "status": row.status,
        "content": row.content_json,
        "model": row.model,
        "pm_reviewed_at": row.pm_reviewed_at.isoformat()
        if row.pm_reviewed_at
        else None,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "client_confirmed_at": row.client_confirmed_at.isoformat()
        if row.client_confirmed_at
        else None,
        "client_note": row.client_note,
        "created_at": row.created_at.isoformat(),
    }


@api_bp.post("/projects/<project_id>/proposals")
@roles_required("pm", "admin")
def generate_proposal(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    latest = _latest(project.id)
    if latest and latest.status == "client_confirmed":
        return error("conflict", "建议书已被客户确认，需先由客户发起修改", 409)

    try:
        content = build_proposal_content(project)
    except ValueError as exc:
        return error("validation_error", str(exc), 400)

    version = (latest.version if latest else 0) + 1
    row = Proposal(
        project_id=project.id,
        version=version,
        status="generated",
        content_json=content,
        model=content.get("model"),
    )
    db.session.add(row)
    fire_project(project, "proposal_generated")
    record_audit(
        "proposal_generated",
        object_type="proposal",
        object_id=row.id,
        project_id=project.id,
        detail={"version": version},
    )
    db.session.commit()

    return jsonify({"data": proposal_payload(row)}), 201


@api_bp.get("/projects/<project_id>/proposals")
@roles_required("pm", "admin")
def list_proposals(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    rows = (
        Proposal.query.filter_by(project_id=project.id)
        .order_by(Proposal.version.desc())
        .all()
    )
    return jsonify(
        {
            "data": [
                {
                    "id": row.id,
                    "version": row.version,
                    "status": row.status,
                    "created_at": row.created_at.isoformat(),
                    "client_confirmed_at": row.client_confirmed_at.isoformat()
                    if row.client_confirmed_at
                    else None,
                }
                for row in rows
            ]
        }
    )


@api_bp.get("/proposals/<proposal_id>")
@roles_required("pm", "admin")
def get_proposal(proposal_id):
    row = db.session.get(Proposal, proposal_id)
    if row is None:
        return error("not_found", "建议书不存在", 404)
    return jsonify({"data": proposal_payload(row)})


@api_bp.post("/proposals/<proposal_id>/review")
@roles_required("pm", "admin")
def review_proposal(proposal_id):
    row = db.session.get(Proposal, proposal_id)
    if row is None:
        return error("not_found", "建议书不存在", 404)

    fire_proposal(row, "review")
    row.pm_reviewed_by = g.current_user.id
    row.pm_reviewed_at = datetime.utcnow()
    record_audit(
        "proposal_reviewed",
        object_type="proposal",
        object_id=row.id,
        project_id=row.project_id,
        detail={"version": row.version},
    )
    db.session.commit()
    return jsonify({"data": proposal_payload(row)})


@api_bp.post("/proposals/<proposal_id>/send")
@roles_required("pm", "admin")
def send_proposal(proposal_id):
    row = db.session.get(Proposal, proposal_id)
    if row is None:
        return error("not_found", "建议书不存在", 404)

    fire_proposal(row, "send")
    row.sent_at = datetime.utcnow()
    record_audit(
        "proposal_sent",
        object_type="proposal",
        object_id=row.id,
        project_id=row.project_id,
        detail={"version": row.version},
    )
    db.session.commit()
    return jsonify({"data": proposal_payload(row)})


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
    if row.role_type not in ROLE_TYPES:
        return None, error("forbidden", "该链接不是客户确认链接", 403)
    return row, None


@api_bp.get("/link/<token>/proposal")
def link_proposal(token):
    row, failure = _client_token(token)
    if failure:
        return failure

    proposal = _latest(row.project_id)
    if proposal is None:
        return error("not_found", "建议书尚未生成", 404)
    if proposal.status not in {"sent", "client_confirmed", "revision_requested"}:
        return error("conflict", "建议书尚未发送给客户", 409)
    return jsonify({"data": proposal_payload(proposal)})


@api_bp.post("/link/<token>/proposal/confirm")
def confirm_proposal(token):
    row, failure = _client_token(token)
    if failure:
        return failure

    proposal = _latest(row.project_id)
    if proposal is None:
        return error("not_found", "建议书尚未生成", 404)
    if proposal.status == "client_confirmed":
        return jsonify({"data": proposal_payload(proposal)})
    if proposal.status != "sent":
        return error("conflict", "当前状态不能确认", 409)

    fire_proposal(proposal, "confirm")
    proposal.client_confirmed_at = datetime.utcnow()
    proposal.client_confirm_ip = client_ip()
    project = db.session.get(Project, row.project_id)
    fire_project(project, "proposal_confirmed")
    record_audit(
        "proposal_confirmed",
        object_type="proposal",
        object_id=proposal.id,
        project_id=row.project_id,
        actor_label=f"client:{row.subject_id or row.id}",
        detail={"version": proposal.version},
    )
    db.session.commit()
    return jsonify({"data": proposal_payload(proposal)})


@api_bp.post("/link/<token>/proposal/revision")
def revise_proposal(token):
    row, failure = _client_token(token)
    if failure:
        return failure

    proposal = _latest(row.project_id)
    if proposal is None:
        return error("not_found", "建议书尚未生成", 404)
    if proposal.status != "sent":
        return error("conflict", "当前状态不能发起修改", 409)

    data = request.get_json(silent=True) or {}
    note = str(data.get("note", "")).strip()
    if not note:
        return error("validation_error", "请填写修改意见", 400)

    fire_proposal(proposal, "revision")
    proposal.client_note = note[:2000]
    project = db.session.get(Project, row.project_id)
    fire_project(project, "proposal_revision_requested")
    record_audit(
        "proposal_revision_requested",
        object_type="proposal",
        object_id=proposal.id,
        project_id=row.project_id,
        actor_label=f"client:{row.subject_id or row.id}",
        detail={"version": proposal.version, "note": note[:200]},
    )
    db.session.commit()
    return jsonify({"data": proposal_payload(proposal)})

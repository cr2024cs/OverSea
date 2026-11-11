from datetime import datetime

from flask import g, jsonify, request

from app.api import api_bp
from app.api.contracts import contract_payload
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import ClientQuote, Contract, Milestone, Project, Proposal
from app.services.audit import record_audit
from app.services.permissions import can_access_project
from app.services.sourcing import catalog_payload, selection_data
from app.services.state_machine import (
    fire_client_quote,
    fire_contract,
    fire_project,
    fire_proposal,
)
from app.utils import client_ip


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    if not can_access_project(g.current_user, project):
        return None, error("forbidden", "无权访问该项目", 403)
    return project, None


def _latest_proposal(project_id):
    return (
        Proposal.query.filter_by(project_id=project_id)
        .filter(Proposal.status.in_(["sent", "client_confirmed", "revision_requested"]))
        .order_by(Proposal.version.desc())
        .first()
    )


def _latest_client_quote(project_id):
    return (
        ClientQuote.query.filter_by(project_id=project_id)
        .filter(ClientQuote.status.in_(["sent", "confirmed"]))
        .order_by(ClientQuote.version.desc())
        .first()
    )


def _latest_contract(project_id):
    return (
        Contract.query.filter_by(project_id=project_id, type="master")
        .filter(Contract.status.in_(["pending_client", "pending_provider", "active"]))
        .order_by(Contract.version.desc())
        .first()
    )


@api_bp.get("/projects/<project_id>/client-portal")
@roles_required("client")
def client_portal(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    proposal = _latest_proposal(project.id)
    quote = _latest_client_quote(project.id)
    contract = _latest_contract(project.id)
    milestones = (
        Milestone.query.filter_by(project_id=project.id)
        .order_by(Milestone.due_date.asc())
        .all()
    )
    catalog = catalog_payload(project)

    return jsonify(
        {
            "data": {
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "client_name": project.client_name,
                    "phase": project.phase,
                    "status": project.status,
                    "archived": project.archived,
                },
                "requirement": {
                    **project.requirement_json,
                    "confirmed_at": project.requirement_confirmed_at.isoformat()
                    if project.requirement_confirmed_at
                    else None,
                }
                if project.requirement_json
                else None,
                "proposal": {
                    "id": proposal.id,
                    "version": proposal.version,
                    "status": proposal.status,
                    "content": proposal.content_json,
                    "client_note": proposal.client_note,
                    "client_confirmed_at": proposal.client_confirmed_at.isoformat()
                    if proposal.client_confirmed_at
                    else None,
                }
                if proposal
                else None,
                "selection": catalog["selection"],
                "service_catalog": catalog["stages"],
                "warnings": catalog["warnings"],
                "client_quote": {
                    "id": quote.id,
                    "version": quote.version,
                    "provider_amount_cents": quote.provider_amount_cents,
                    "lawyer_amount_cents": quote.lawyer_amount_cents,
                    "management_fee_rate": quote.management_fee_rate,
                    "management_fee_cents": quote.management_fee_cents,
                    "total_cents": quote.total_cents,
                    "currency": quote.currency,
                    "status": quote.status,
                    "confirmed_at": quote.confirmed_at.isoformat()
                    if quote.confirmed_at
                    else None,
                }
                if quote
                else None,
                "contract": contract_payload(contract) if contract else None,
                "milestones": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "status": row.status,
                        "due_date": row.due_date.isoformat() if row.due_date else None,
                        "client_confirmed_at": row.client_confirmed_at.isoformat()
                        if row.client_confirmed_at
                        else None,
                    }
                    for row in milestones
                ],
            }
        }
    )


@api_bp.post("/projects/<project_id>/client-portal/requirement/confirm")
@roles_required("client")
def client_confirm_requirement(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    if not project.requirement_json:
        return error("not_found", "需求确认书尚未生成", 404)
    if project.requirement_confirmed_at is None:
        project.requirement_confirmed_at = datetime.utcnow()
        record_audit(
            "requirement_confirmed",
            object_type="project",
            object_id=project.id,
            project_id=project.id,
            actor_label=f"client:{g.current_user.email}",
        )
        db.session.commit()
    return jsonify(
        {"data": {"confirmed_at": project.requirement_confirmed_at.isoformat()}}
    )


@api_bp.post("/projects/<project_id>/client-portal/proposal/confirm")
@roles_required("client")
def client_confirm_proposal(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    proposal = _latest_proposal(project.id)
    if proposal is None:
        return error("not_found", "建议书尚未发送", 404)
    if proposal.status == "client_confirmed":
        return jsonify(
            {"data": {"confirmed_at": proposal.client_confirmed_at.isoformat()}}
        )
    if proposal.status != "sent":
        return error("conflict", "当前状态不能确认", 409)

    fire_proposal(proposal, "confirm")
    proposal.client_confirmed_at = datetime.utcnow()
    proposal.client_confirm_ip = client_ip()
    fire_project(project, "proposal_confirmed")
    record_audit(
        "proposal_confirmed",
        object_type="proposal",
        object_id=proposal.id,
        project_id=project.id,
        actor_label=f"client:{g.current_user.email}",
    )
    db.session.commit()
    return jsonify(
        {"data": {"confirmed_at": proposal.client_confirmed_at.isoformat()}}
    )


@api_bp.post("/projects/<project_id>/client-portal/proposal/revision")
@roles_required("client")
def client_revise_proposal(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    proposal = _latest_proposal(project.id)
    if proposal is None or proposal.status != "sent":
        return error("conflict", "当前状态不能发起修改", 409)
    data = request.get_json(silent=True) or {}
    note = str(data.get("note", "")).strip()
    if not note:
        return error("validation_error", "请填写修改意见", 400)
    fire_proposal(proposal, "revision")
    proposal.client_note = note[:2000]
    fire_project(project, "proposal_revision_requested")
    record_audit(
        "proposal_revision_requested",
        object_type="proposal",
        object_id=proposal.id,
        project_id=project.id,
        actor_label=f"client:{g.current_user.email}",
        detail={"note": note[:200]},
    )
    db.session.commit()
    return jsonify({"data": {"status": proposal.status}})


@api_bp.post("/projects/<project_id>/client-portal/quote/confirm")
@roles_required("client")
def client_confirm_quote(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    quote = _latest_client_quote(project.id)
    if quote is None:
        return error("not_found", "总报价尚未发送", 404)
    if quote.status == "confirmed":
        return jsonify({"data": {"confirmed_at": quote.confirmed_at.isoformat()}})
    if quote.status != "sent":
        return error("conflict", "当前状态不能确认", 409)
    fire_client_quote(quote, "confirm")
    quote.confirmed_at = datetime.utcnow()
    quote.confirm_ip = client_ip()
    fire_project(project, "client_quote_confirmed")
    project.total_quote_json = {
        "version": quote.version,
        "provider_amount_cents": quote.provider_amount_cents,
        "lawyer_amount_cents": quote.lawyer_amount_cents,
        "management_fee_cents": quote.management_fee_cents,
        "total_cents": quote.total_cents,
        "currency": quote.currency,
        "status": "confirmed",
    }
    record_audit(
        "client_quote_confirmed",
        object_type="client_quote",
        object_id=quote.id,
        project_id=project.id,
        actor_label=f"client:{g.current_user.email}",
    )
    db.session.commit()
    return jsonify({"data": {"confirmed_at": quote.confirmed_at.isoformat()}})


@api_bp.post("/projects/<project_id>/client-portal/contract/confirm")
@roles_required("client")
def client_confirm_contract(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    contract = _latest_contract(project.id)
    if contract is None:
        return error("not_found", "合同尚未发送", 404)
    if contract.client_confirmed_at is not None:
        return jsonify(
            {"data": {"confirmed_at": contract.client_confirmed_at.isoformat()}}
        )
    if contract.status != "pending_client":
        return error("conflict", "当前状态不能确认", 409)
    fire_contract(contract, "client_confirm")
    contract.client_confirmed_at = datetime.utcnow()
    contract.client_confirm_ip = client_ip()
    record_audit(
        "contract_client_confirmed",
        object_type="contract",
        object_id=contract.id,
        project_id=project.id,
        actor_label=f"client:{g.current_user.email}",
    )
    db.session.commit()
    return jsonify(
        {"data": {"confirmed_at": contract.client_confirmed_at.isoformat()}}
    )


@api_bp.post("/projects/<project_id>/client-portal/milestones/<milestone_id>/confirm")
@roles_required("client")
def client_portal_confirm_milestone(project_id, milestone_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    milestone = db.session.get(Milestone, milestone_id)
    if milestone is None or milestone.project_id != project.id:
        return error("not_found", "节点不存在", 404)
    if milestone.client_confirmed_at is None:
        milestone.client_confirmed_at = datetime.utcnow()
        milestone.client_confirm_ip = client_ip()
        record_audit(
            "milestone_client_confirmed",
            object_type="milestone",
            object_id=milestone.id,
            project_id=project.id,
            actor_label=f"client:{g.current_user.email}",
        )
        db.session.commit()
    return jsonify(
        {"data": {"confirmed_at": milestone.client_confirmed_at.isoformat()}}
    )

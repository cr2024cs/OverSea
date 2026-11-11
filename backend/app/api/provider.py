from datetime import datetime

from flask import g, jsonify, request

from app.api import api_bp
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import (
    ClientQuote,
    Contract,
    Milestone,
    Project,
    Provider,
    QueryLetter,
    Quote,
    RFP,
    Task,
)
from app.services.audit import record_audit
from app.services.quotes import parse_quote_text
from app.services.state_machine import (
    fire_contract,
    fire_milestone,
    fire_project,
    fire_quote,
    fire_query_letter,
    fire_rfp,
)
from app.utils import client_ip


def _provider_user():
    user = g.current_user
    if user.role != "provider" or not user.provider_id:
        return None, error("forbidden", "当前账号未绑定服务商", 403)
    return user, None


def _project_summary(project):
    return {
        "id": project.id,
        "name": project.name,
        "country": project.country,
        "industry": project.industry,
        "phase": project.phase,
        "status": project.status,
    }


@api_bp.get("/provider/workbench")
@roles_required("provider")
def provider_workbench():
    user, failure = _provider_user()
    if failure:
        return failure

    rfps = (
        RFP.query.filter_by(provider_id=user.provider_id)
        .filter(RFP.status.in_(["sent", "replied"]))
        .order_by(RFP.sent_at.desc())
        .all()
    )
    rfp_payload = []
    for rfp in rfps:
        project = db.session.get(Project, rfp.project_id)
        task = db.session.get(Task, rfp.task_id)
        quote = Quote.query.filter_by(rfp_id=rfp.id).first()
        rfp_payload.append(
            {
                "id": rfp.id,
                "project": _project_summary(project) if project else None,
                "task_code": task.code if task else None,
                "task_name": task.name if task else None,
                "status": rfp.status,
                "content_zh": rfp.content_zh,
                "content_en": rfp.content_en,
                "sent_at": rfp.sent_at.isoformat() if rfp.sent_at else None,
                "quote": {
                    "id": quote.id,
                    "currency": quote.currency,
                    "amount_cents": quote.amount_cents,
                    "status": quote.status,
                }
                if quote
                else None,
            }
        )

    contracts = []
    for row in Contract.query.filter_by(type="provider").all():
        if (row.scope_json or {}).get("provider_id") != user.provider_id:
            continue
        master = Contract.query.filter_by(
            project_id=row.project_id, type="master", version=row.version
        ).first()
        project = db.session.get(Project, row.project_id)
        contracts.append(
            {
                "id": row.id,
                "project": _project_summary(project) if project else None,
                "version": row.version,
                "total_cents": row.total_cents,
                "currency": row.currency,
                "status": row.status,
                "provider_confirmed_at": row.provider_confirmed_at.isoformat()
                if row.provider_confirmed_at
                else None,
                "client_confirmed_at": master.client_confirmed_at.isoformat()
                if master and master.client_confirmed_at
                else None,
                "task_codes": (row.scope_json or {}).get("task_codes", []),
                "terms": row.terms_json,
                "file_hash": row.file_hash,
            }
        )

    milestones = (
        Milestone.query.filter_by(provider_id=user.provider_id)
        .order_by(Milestone.due_date.asc())
        .all()
    )
    milestone_payload = []
    for row in milestones:
        project = db.session.get(Project, row.project_id)
        task = db.session.get(Task, row.task_id) if row.task_id else None
        milestone_payload.append(
            {
                "id": row.id,
                "project": _project_summary(project) if project else None,
                "task_code": task.code if task else None,
                "task_name": task.name if task else row.name,
                "status": row.status,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "deliverable": row.deliverable,
                "acceptance_criteria": row.acceptance_criteria,
                "submission_note": row.submission_note,
                "pm_review_status": row.pm_review_status,
                "pm_review_note": row.pm_review_note,
            }
        )

    letters = (
        QueryLetter.query.filter_by(provider_id=user.provider_id)
        .filter(QueryLetter.status.in_(["sent", "replied"]))
        .order_by(QueryLetter.sent_at.desc())
        .all()
    )
    letter_payload = []
    for letter in letters:
        ids = letter.finding_ids_json or []
        from app.models import Finding

        findings = Finding.query.filter(Finding.id.in_(ids)).all() if ids else []
        letter_payload.append(
            {
                "id": letter.id,
                "status": letter.status,
                "content": letter.content,
                "findings": [
                    {
                        "id": finding.id,
                        "category": finding.category,
                        "severity": finding.severity,
                        "quote_text": finding.quote_text,
                        "question_zh": finding.question_zh,
                        "reply_text": finding.reply_text,
                    }
                    for finding in findings
                ],
            }
        )

    return jsonify(
        {
            "data": {
                "provider": {"id": user.provider_id, "name": user.company},
                "rfps": rfp_payload,
                "contracts": contracts,
                "milestones": milestone_payload,
                "query_letters": letter_payload,
            }
        }
    )


@api_bp.post("/provider/rfps/<rfp_id>/quote")
@roles_required("provider")
def provider_submit_quote(rfp_id):
    user, failure = _provider_user()
    if failure:
        return failure
    rfp = db.session.get(RFP, rfp_id)
    if rfp is None or rfp.provider_id != user.provider_id:
        return error("not_found", "询价书不存在", 404)
    if rfp.status not in {"sent", "replied"}:
        return error("conflict", "询价书尚未发送", 409)

    data = request.get_json(silent=True) or {}
    raw_text = str(data.get("raw_text", "")).strip()
    parsed = parse_quote_text(raw_text) if raw_text else None
    amount_cents = data.get("amount_cents")
    currency = str(data.get("currency", "CNY")).upper()
    if amount_cents in (None, "") and parsed:
        amount_cents = parsed["amount_cents"]
        currency = parsed["currency"]
    try:
        amount_cents = int(amount_cents)
    except (TypeError, ValueError):
        return error("validation_error", "请填写报价金额或粘贴可识别的报价文本", 400)
    if amount_cents <= 0:
        return error("validation_error", "报价金额必须大于 0", 400)

    quote = Quote.query.filter_by(rfp_id=rfp.id).first()
    if quote is None:
        quote = Quote(rfp_id=rfp.id, provider_id=rfp.provider_id, task_id=rfp.task_id)
        db.session.add(quote)
    quote.currency = currency
    quote.amount_cents = amount_cents
    quote.items_json = data.get("items") or [
        {"name": "报价总额", "amount_cents": amount_cents}
    ]
    quote.assumptions = data.get("assumptions")
    quote.exclusions = data.get("exclusions")
    quote.payment_terms = data.get("payment_terms")
    quote.raw_text = raw_text or None
    fire_quote(quote)
    fire_rfp(rfp, "reply")
    record_audit(
        "quote_submitted",
        object_type="quote",
        object_id=quote.id,
        project_id=rfp.project_id,
        actor_label=f"provider:{user.id}",
        detail={"amount_cents": amount_cents, "currency": currency},
    )
    db.session.commit()
    return jsonify({"data": {"id": quote.id, "amount_cents": amount_cents}}), 201


@api_bp.post("/provider/contracts/<contract_id>/confirm")
@roles_required("provider")
def provider_confirm_contract(contract_id):
    user, failure = _provider_user()
    if failure:
        return failure
    contract = db.session.get(Contract, contract_id)
    if contract is None or contract.type != "provider":
        return error("not_found", "合同不存在", 404)
    if (contract.scope_json or {}).get("provider_id") != user.provider_id:
        return error("forbidden", "无权确认该合同", 403)
    master = Contract.query.filter_by(
        project_id=contract.project_id, type="master", version=contract.version
    ).first()
    if master is None or master.client_confirmed_at is None:
        return error("conflict", "客户尚未确认，服务商不能先确认", 409)

    if contract.provider_confirmed_at is None:
        contract.provider_confirmed_at = datetime.utcnow()
        contract.provider_confirm_ip = client_ip()

    siblings = Contract.query.filter_by(
        project_id=contract.project_id, type="provider", version=contract.version
    ).all()
    if all(row.provider_confirmed_at is not None for row in siblings):
        master.provider_confirmed_at = datetime.utcnow()
        fire_contract(master, "activate")
        project = db.session.get(Project, master.project_id)
        fire_project(project, "contracts_activated")
    record_audit(
        "contract_provider_confirmed",
        object_type="contract",
        object_id=contract.id,
        project_id=contract.project_id,
        actor_label=f"provider:{user.id}",
    )
    db.session.commit()
    return jsonify({"data": {"id": contract.id, "status": master.status}})


@api_bp.post("/provider/milestones/<milestone_id>/submission")
@roles_required("provider")
def provider_submit_milestone(milestone_id):
    user, failure = _provider_user()
    if failure:
        return failure
    milestone = db.session.get(Milestone, milestone_id)
    if milestone is None or milestone.provider_id != user.provider_id:
        return error("not_found", "节点不存在", 404)

    data = request.get_json(silent=True) or {}
    milestone.submission_note = str(data.get("note", "")).strip()
    milestone.submission_files_json = data.get("files") or []
    milestone.submitted_at = datetime.utcnow()
    fire_milestone(milestone, "submit")
    milestone.pm_review_status = "pending"
    milestone.pm_review_note = None
    record_audit(
        "milestone_submitted",
        object_type="milestone",
        object_id=milestone.id,
        project_id=milestone.project_id,
        actor_label=f"provider:{user.id}",
    )
    db.session.commit()
    return jsonify({"data": {"id": milestone.id, "status": milestone.status}})


@api_bp.post("/provider/query-letters/<letter_id>/reply")
@roles_required("provider")
def provider_reply_letter(letter_id):
    user, failure = _provider_user()
    if failure:
        return failure
    letter = db.session.get(QueryLetter, letter_id)
    if letter is None or letter.provider_id != user.provider_id:
        return error("not_found", "质询函不存在", 404)
    if letter.status not in {"sent", "replied"}:
        return error("conflict", "质询函当前不可回复", 409)

    from app.models import Finding

    data = request.get_json(silent=True) or {}
    ids = set(letter.finding_ids_json or [])
    for item in data.get("replies") or []:
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
        fire_query_letter(letter, "reply")
    record_audit(
        "query_letter_replied",
        object_type="query_letter",
        object_id=letter.id,
        project_id=letter.project_id,
        actor_label=f"provider:{user.id}",
    )
    db.session.commit()
    return jsonify({"data": {"id": letter.id, "status": letter.status}})

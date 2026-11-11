import hashlib
import json
from datetime import date, datetime, timedelta

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
    Quote,
    RFP,
    Task,
)
from app.services.audit import record_audit
from app.services.sourcing import selection_data
from app.services.state_machine import fire_contract, fire_project
from app.services.tokens import resolve_access_token
from app.utils import client_ip

SLA_TERMS = {
    "response_hours": 48,
    "delivery_standard": "按节点交付物清单与验收标准提交",
    "rework_limit": 2,
    "acceptance": "PM 初审 + 需要时专家盲评 + 客户确认",
    "overdue": "逾期 1 天提醒 PM，3 天升级管理员，7 天评估更换服务商",
    "confidentiality": "双方对项目资料保密，未经许可不得披露客户名称",
    "conflict": "服务商须披露与本项目相关的利益冲突",
}

DISCLAIMER = "本确认为委托确认，不构成电子签名；正式合同由平台与关联律所线下签署。"


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    return project, None


def _latest_master(project_id):
    return (
        Contract.query.filter_by(project_id=project_id, type="master")
        .order_by(Contract.version.desc())
        .first()
    )


def _provider_contracts(project_id, version):
    return (
        Contract.query.filter_by(
            project_id=project_id, type="provider", version=version
        )
        .order_by(Contract.created_at.asc())
        .all()
    )


def _milestone_payload(row):
    task = db.session.get(Task, row.task_id) if row.task_id else None
    provider = db.session.get(Provider, row.provider_id) if row.provider_id else None
    return {
        "id": row.id,
        "task_code": task.code if task else None,
        "task_name": task.name if task else row.name,
        "provider_name": provider.name if provider else None,
        "deliverable": row.deliverable,
        "acceptance_criteria": row.acceptance_criteria,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "status": row.status,
        "acceptor_type": row.acceptor_type,
        "grace_days": row.grace_days,
        "rounds": row.rounds,
    }


def contract_payload(row, include_milestones=True):
    provider = (
        db.session.get(Provider, (row.scope_json or {}).get("provider_id"))
        if row.type == "provider"
        else None
    )
    payload = {
        "id": row.id,
        "version": row.version,
        "type": row.type,
        "status": row.status,
        "total_cents": row.total_cents,
        "currency": row.currency,
        "scope": row.scope_json or {},
        "terms": row.terms_json or {},
        "file_hash": row.file_hash,
        "pm_reviewed_at": row.pm_reviewed_at.isoformat() if row.pm_reviewed_at else None,
        "client_confirmed_at": row.client_confirmed_at.isoformat()
        if row.client_confirmed_at
        else None,
        "provider_confirmed_at": row.provider_confirmed_at.isoformat()
        if row.provider_confirmed_at
        else None,
        "created_at": row.created_at.isoformat(),
    }
    if provider is not None:
        payload["provider_name"] = provider.name
        payload["provider_id"] = provider.id
    if row.type == "master" and include_milestones:
        milestones = (
            Milestone.query.filter_by(contract_id=row.id)
            .order_by(Milestone.due_date.asc())
            .all()
        )
        payload["milestones"] = [_milestone_payload(item) for item in milestones]
        payload["provider_contracts"] = [
            contract_payload(item, include_milestones=False)
            for item in _provider_contracts(row.project_id, row.version)
        ]
    return payload


def _task_provider_map(project_id):
    rows = (
        db.session.query(Quote, RFP)
        .join(RFP, Quote.rfp_id == RFP.id)
        .filter(RFP.project_id == project_id)
        .order_by(Quote.amount_cents.asc())
        .all()
    )
    mapping = {}
    for quote, _rfp in rows:
        mapping.setdefault(quote.task_id, quote.provider_id)
    if not mapping:
        for rfp in RFP.query.filter_by(project_id=project_id).all():
            if rfp.status in {"sent", "replied"}:
                mapping.setdefault(rfp.task_id, rfp.provider_id)
    return mapping


def _provider_amount(project_id, provider_id, task_ids):
    rows = (
        db.session.query(Quote, RFP)
        .join(RFP, Quote.rfp_id == RFP.id)
        .filter(
            RFP.project_id == project_id,
            Quote.provider_id == provider_id,
            Quote.task_id.in_(task_ids),
        )
        .all()
    )
    lowest = {}
    for quote, _rfp in rows:
        current = lowest.get(quote.task_id)
        if current is None or quote.amount_cents < current:
            lowest[quote.task_id] = quote.amount_cents
    return sum(lowest.values())


@api_bp.post("/projects/<project_id>/contracts")
@roles_required("pm", "admin")
def generate_contracts(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    client_quote = (
        ClientQuote.query.filter_by(project_id=project.id)
        .order_by(ClientQuote.version.desc())
        .first()
    )
    if client_quote is None or client_quote.status != "confirmed":
        return error("validation_error", "请先完成客户总报价确认", 400)

    codes = selection_data(project)["codes"]
    if not codes:
        return error("validation_error", "请先选择服务", 400)

    tasks = (
        Task.query.filter(Task.project_id == project.id, Task.code.in_(codes))
        .order_by(Task.stage_no.asc(), Task.code.asc())
        .all()
    )
    if not tasks:
        return error("validation_error", "未找到已选服务对应任务", 400)

    task_provider = _task_provider_map(project.id)
    provider_ids = sorted({pid for pid in task_provider.values() if pid})
    if not provider_ids:
        return error("validation_error", "请先完成询价与报价，再生成合同", 400)

    latest = _latest_master(project.id)
    version = (latest.version if latest else 0) + 1
    master = Contract(
        project_id=project.id,
        version=version,
        type="master",
        scope_json={
            "codes": codes,
            "task_count": len(tasks),
            "provider_ids": provider_ids,
            "client_quote_version": client_quote.version,
        },
        total_cents=client_quote.total_cents,
        currency=client_quote.currency,
        terms_json={
            "sla": SLA_TERMS,
            "client_terms": "客户与平台的总包关系；服务范围与总价以本确认单为准。",
            "provider_terms": "平台与服务商的背靠背关系；范围、报价与交付以服务商委托单为准。",
            "disclaimer": DISCLAIMER,
        },
        status="draft",
    )
    db.session.add(master)
    db.session.flush()

    provider_contracts = []
    for provider_id in provider_ids:
        provider_tasks = [
            task for task in tasks if task_provider.get(task.id) == provider_id
        ]
        if not provider_tasks:
            continue
        task_ids = [task.id for task in provider_tasks]
        row = Contract(
            project_id=project.id,
            version=version,
            type="provider",
            scope_json={
                "provider_id": provider_id,
                "task_codes": [task.code for task in provider_tasks],
            },
            total_cents=_provider_amount(project.id, provider_id, task_ids),
            currency=client_quote.currency,
            terms_json={"sla": SLA_TERMS, "disclaimer": DISCLAIMER},
            status="draft",
        )
        db.session.add(row)
        provider_contracts.append(row)
    db.session.flush()

    milestones = []
    for task in tasks:
        provider_id = task_provider.get(task.id)
        milestone = Milestone(
            project_id=project.id,
            task_id=task.id,
            contract_id=master.id,
            provider_id=provider_id,
            name=task.name,
            deliverable="；".join(task.deliverables_json or []),
            acceptance_criteria=task.acceptance_criteria,
            due_date=task.due_date or (date.today() + timedelta(days=task.duration_days)),
            status="pending_submission",
            acceptor_type="expert" if task.is_critical else "pm",
            grace_days=3,
        )
        db.session.add(milestone)
        milestones.append(milestone)
    db.session.flush()

    hash_source = {
        "master": {
            "version": version,
            "scope": master.scope_json,
            "total_cents": master.total_cents,
            "terms": master.terms_json,
        },
        "providers": [
            {
                "provider_id": row.scope_json.get("provider_id"),
                "task_codes": row.scope_json.get("task_codes"),
                "total_cents": row.total_cents,
            }
            for row in provider_contracts
        ],
        "milestones": [
            {
                "task_code": (
                    db.session.get(Task, item.task_id).code if item.task_id else None
                ),
                "name": item.name,
                "due_date": item.due_date.isoformat() if item.due_date else None,
                "criteria": item.acceptance_criteria,
            }
            for item in milestones
        ],
    }
    master.file_hash = hashlib.sha256(
        json.dumps(hash_source, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    for row in provider_contracts:
        row.file_hash = master.file_hash

    fire_project(project, "contract_generated")
    record_audit(
        "contracts_generated",
        object_type="contract",
        object_id=master.id,
        project_id=project.id,
        detail={
            "version": version,
            "milestones": len(milestones),
            "providers": len(provider_contracts),
        },
    )
    db.session.commit()
    return jsonify({"data": contract_payload(master)}), 201


@api_bp.get("/projects/<project_id>/contracts")
@roles_required("pm", "admin")
def list_contracts(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    rows = (
        Contract.query.filter_by(project_id=project.id, type="master")
        .order_by(Contract.version.desc())
        .all()
    )
    return jsonify({"data": [contract_payload(row) for row in rows]})


@api_bp.get("/contracts/<contract_id>")
@roles_required("pm", "admin")
def get_contract(contract_id):
    row = db.session.get(Contract, contract_id)
    if row is None:
        return error("not_found", "合同不存在", 404)
    return jsonify({"data": contract_payload(row)})


@api_bp.post("/contracts/<contract_id>/review")
@roles_required("pm", "admin")
def review_contract(contract_id):
    row = db.session.get(Contract, contract_id)
    if row is None:
        return error("not_found", "合同不存在", 404)
    if row.type != "master":
        return error("validation_error", "只能复核总包合同", 400)
    fire_contract(row, "review")
    row.pm_reviewed_by = g.current_user.id
    row.pm_reviewed_at = datetime.utcnow()
    record_audit(
        "contract_reviewed",
        object_type="contract",
        object_id=row.id,
        project_id=row.project_id,
        detail={"version": row.version},
    )
    db.session.commit()
    return jsonify({"data": contract_payload(row)})


def _contract_context(raw_token):
    token_row, reason = resolve_access_token(raw_token)
    if token_row is None:
        messages = {
            "invalid": ("invalid_access_token", "链接无效"),
            "revoked": ("access_token_revoked", "链接已作废"),
            "expired": ("access_token_expired", "链接已过期"),
        }
        code, message = messages.get(reason, ("invalid_access_token", "链接无效"))
        return None, None, None, error(code, message, 401)

    master = _latest_master(token_row.project_id)
    if master is None:
        return None, None, None, error("not_found", "合同尚未生成", 404)

    provider_contract = None
    if token_row.role_type == "provider":
        for row in _provider_contracts(master.project_id, master.version):
            if (row.scope_json or {}).get("provider_id") == token_row.subject_id:
                provider_contract = row
                break
        if provider_contract is None:
            return None, None, None, error("forbidden", "令牌未绑定到本项目服务商", 403)
    elif token_row.role_type != "client":
        return None, None, None, error("forbidden", "该链接不能访问合同", 403)

    return token_row, master, provider_contract, None


@api_bp.get("/link/<token>/contract")
def link_contract(token):
    token_row, master, provider_contract, failure = _contract_context(token)
    if failure:
        return failure

    payload = contract_payload(master)
    payload["actor"] = token_row.role_type
    if provider_contract is not None:
        payload["provider_contract"] = contract_payload(
            provider_contract, include_milestones=False
        )
    return jsonify({"data": payload})


@api_bp.post("/link/<token>/contract/confirm")
def confirm_contract(token):
    token_row, master, provider_contract, failure = _contract_context(token)
    if failure:
        return failure

    if token_row.role_type == "client":
        if master.client_confirmed_at is None:
            if master.status != "pending_client":
                return error("conflict", "当前状态不能由客户确认", 409)
            master.client_confirmed_at = datetime.utcnow()
            master.client_confirm_ip = client_ip()
            fire_contract(master, "client_confirm")
            record_audit(
                "contract_client_confirmed",
                object_type="contract",
                object_id=master.id,
                project_id=master.project_id,
                actor_label=f"client:{token_row.subject_id or token_row.id}",
            )
            db.session.commit()
        payload = contract_payload(master)
        payload["actor"] = "client"
        return jsonify({"data": payload})

    if master.client_confirmed_at is None:
        return error("conflict", "客户尚未确认，服务商不能先确认", 409)
    if master.status == "active":
        payload = contract_payload(master)
        payload["actor"] = "provider"
        payload["provider_contract"] = contract_payload(
            provider_contract, include_milestones=False
        )
        return jsonify({"data": payload})
    if provider_contract.provider_confirmed_at is None:
        provider_contract.provider_confirmed_at = datetime.utcnow()
        provider_contract.provider_confirm_ip = client_ip()

    all_confirmed = all(
        row.provider_confirmed_at is not None
        for row in _provider_contracts(master.project_id, master.version)
    )
    if all_confirmed:
        master.provider_confirmed_at = datetime.utcnow()
        fire_contract(master, "activate")
        project = db.session.get(Project, master.project_id)
        fire_project(project, "contracts_activated")

    record_audit(
        "contract_provider_confirmed",
        object_type="contract",
        object_id=provider_contract.id,
        project_id=master.project_id,
        actor_label=f"provider:{token_row.subject_id}",
    )
    db.session.commit()
    payload = contract_payload(master)
    payload["actor"] = "provider"
    payload["provider_contract"] = contract_payload(
        provider_contract, include_milestones=False
    )
    return jsonify({"data": payload})

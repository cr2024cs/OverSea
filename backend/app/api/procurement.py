import secrets

from flask import current_app, g, jsonify, request

from app.api import api_bp
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import (
    Candidate,
    ClientQuote,
    Fact,
    Project,
    Provider,
    Quote,
    RFP,
    Task,
    TaskTemplate,
)
from app.services.audit import record_audit
from app.services.quotes import parse_quote_text, provider_amount_for_project
from app.services.sourcing import selection_data
from app.services.state_machine import (
    fire_client_quote,
    fire_project,
    fire_quote,
    fire_rfp,
)
from app.services.tokens import resolve_access_token
from app.utils import client_ip


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
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


def _rfp_content(project, task, template):
    facts = Fact.query.filter_by(project_id=project.id).limit(6).all()
    fact_lines = "\n".join(f"- {fact.key}: {fact.value}" for fact in facts)
    deliverables = "、".join(template.deliverables_json or []) if template else task.name
    zh = f"""询价书（演示）

项目：{project.name}
客户名称：已隐去
任务：{task.code} {task.name}
工作范围：{deliverables}
项目事实摘要：
{fact_lines}

请提交：分项报价、币种、假设、不含项、付款条件、拟派承办人。
利益冲突：请披露与本项目相关的利益冲突。
回复截止：发送后 14 天。
"""
    en = f"""Request for Proposal (Demo)

Project: {project.name}
Client: Withheld
Task: {task.code} {task.name}
Scope: {deliverables}
Key facts:
{fact_lines}

Please provide: itemized pricing, currency, assumptions, exclusions, payment terms and proposed team.
Conflicts of interest: please disclose any conflict related to this project.
Response deadline: 14 days after sending.
"""
    return zh, en


def _rfp_payload(row):
    task = db.session.get(Task, row.task_id)
    provider = db.session.get(Provider, row.provider_id)
    return {
        "id": row.id,
        "task_code": task.code if task else None,
        "task_name": task.name if task else None,
        "provider_id": row.provider_id,
        "provider_name": provider.name if provider else None,
        "version": row.version,
        "status": row.status,
        "content_zh": row.content_zh,
        "content_en": row.content_en,
        "token": row.token,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "link": f"/rfp-link/{row.token}" if row.token else None,
    }


@api_bp.post("/projects/<project_id>/rfps")
@roles_required("pm", "admin")
def create_rfps(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    codes = data.get("task_codes") or selection_data(project)["codes"]
    provider_ids = data.get("provider_ids") or []
    if not codes:
        return error("validation_error", "请先选择服务，再生成询价书", 400)

    tasks = Task.query.filter(
        Task.project_id == project.id, Task.code.in_(codes)
    ).all()
    if not tasks:
        return error("validation_error", "未找到对应任务", 400)

    templates = {row.code: row for row in TaskTemplate.query.filter_by(enabled=True).all()}
    created = []
    for task in sorted(tasks, key=lambda item: item.code):
        candidate_query = Candidate.query.filter_by(
            project_id=project.id, task_id=task.id, status="shortlisted"
        )
        if provider_ids:
            candidate_query = candidate_query.filter(
                Candidate.provider_id.in_(provider_ids)
            )
        candidates = candidate_query.all()
        for candidate in candidates:
            if candidate.provider_id is None:
                continue
            existing = RFP.query.filter_by(
                project_id=project.id,
                task_id=task.id,
                provider_id=candidate.provider_id,
            ).first()
            if existing is not None:
                created.append(existing)
                continue
            zh, en = _rfp_content(project, task, templates.get(task.code))
            row = RFP(
                project_id=project.id,
                task_id=task.id,
                provider_id=candidate.provider_id,
                version=1,
                content_zh=zh,
                content_en=en,
                status="draft",
                token=secrets.token_urlsafe(48),
            )
            db.session.add(row)
            created.append(row)

    if not created:
        return error("validation_error", "请先生成候选服务商，再创建询价书", 400)

    record_audit(
        "rfps_created",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        detail={"count": len(created)},
    )
    db.session.commit()
    return jsonify({"data": [_rfp_payload(row) for row in created]}), 201


@api_bp.get("/projects/<project_id>/rfps")
@roles_required("pm", "admin")
def list_rfps(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    rows = (
        RFP.query.filter_by(project_id=project.id)
        .order_by(RFP.created_at.desc())
        .all()
    )
    return jsonify({"data": [_rfp_payload(row) for row in rows]})


@api_bp.post("/rfps/<rfp_id>/approve")
@roles_required("pm", "admin")
def approve_rfp(rfp_id):
    row = db.session.get(RFP, rfp_id)
    if row is None:
        return error("not_found", "询价书不存在", 404)
    fire_rfp(row, "approve")
    record_audit(
        "rfp_approved",
        object_type="rfp",
        object_id=row.id,
        project_id=row.project_id,
    )
    db.session.commit()
    return jsonify({"data": _rfp_payload(row)})


@api_bp.post("/rfps/<rfp_id>/send")
@roles_required("pm", "admin")
def send_rfp(rfp_id):
    row = db.session.get(RFP, rfp_id)
    if row is None:
        return error("not_found", "询价书不存在", 404)
    from datetime import datetime

    fire_rfp(row, "send")
    row.sent_at = datetime.utcnow()
    record_audit(
        "rfp_sent",
        object_type="rfp",
        object_id=row.id,
        project_id=row.project_id,
    )
    db.session.commit()
    return jsonify({"data": _rfp_payload(row)})


@api_bp.get("/rfp-link/<token>")
def rfp_link(token):
    row = RFP.query.filter_by(token=token).first()
    if row is None:
        return error("not_found", "询价链接无效", 404)
    if row.status not in {"sent", "replied"}:
        return error("conflict", "询价书尚未发送", 409)

    from datetime import datetime

    if row.opened_at is None:
        row.opened_at = datetime.utcnow()
        db.session.commit()

    task = db.session.get(Task, row.task_id)
    quote = Quote.query.filter_by(rfp_id=row.id).first()
    return jsonify(
        {
            "data": {
                "id": row.id,
                "task_code": task.code if task else None,
                "task_name": task.name if task else None,
                "status": row.status,
                "content_zh": row.content_zh,
                "content_en": row.content_en,
                "quote": {
                    "id": quote.id,
                    "currency": quote.currency,
                    "amount_cents": quote.amount_cents,
                    "raw_text": quote.raw_text,
                }
                if quote
                else None,
            }
        }
    )


@api_bp.post("/rfp-link/<token>/quote")
def submit_rfp_quote(token):
    row = RFP.query.filter_by(token=token).first()
    if row is None:
        return error("not_found", "询价链接无效", 404)
    if row.status not in {"sent", "replied"}:
        return error("conflict", "询价书尚未发送", 409)

    data = request.get_json(silent=True) or {}
    raw_text = str(data.get("raw_text", "")).strip()
    amount_cents = data.get("amount_cents")
    currency = str(data.get("currency", "CNY")).upper()
    parsed = parse_quote_text(raw_text) if raw_text else None

    if amount_cents in (None, "") and parsed:
        amount_cents = parsed["amount_cents"]
        currency = parsed["currency"]
    try:
        amount_cents = int(amount_cents)
    except (TypeError, ValueError):
        return error("validation_error", "请填写报价金额或粘贴可识别的报价文本", 400)
    if amount_cents <= 0:
        return error("validation_error", "报价金额必须大于 0", 400)

    items = data.get("items")
    if not items:
        items = [{"name": "报价总额", "amount_cents": amount_cents}]

    quote = Quote.query.filter_by(rfp_id=row.id).first()
    if quote is None:
        quote = Quote(rfp_id=row.id, provider_id=row.provider_id, task_id=row.task_id)
        db.session.add(quote)
    quote.currency = currency
    quote.amount_cents = amount_cents
    quote.items_json = items
    quote.assumptions = data.get("assumptions")
    quote.exclusions = data.get("exclusions")
    quote.payment_terms = data.get("payment_terms")
    quote.raw_text = raw_text or None
    fire_quote(quote)
    fire_rfp(row, "reply")

    record_audit(
        "quote_submitted",
        object_type="quote",
        object_id=quote.id,
        project_id=row.project_id,
        actor_label=f"provider:{row.provider_id}",
        detail={"amount_cents": amount_cents, "currency": currency},
    )
    db.session.commit()
    return jsonify(
        {
            "data": {
                "id": quote.id,
                "currency": quote.currency,
                "amount_cents": quote.amount_cents,
                "status": quote.status,
            }
        }
    ), 201


@api_bp.patch("/quotes/<quote_id>")
@roles_required("pm", "admin")
def update_quote(quote_id):
    quote = db.session.get(Quote, quote_id)
    if quote is None:
        return error("not_found", "报价不存在", 404)

    data = request.get_json(silent=True) or {}
    if "amount_cents" in data:
        try:
            quote.amount_cents = int(data["amount_cents"])
        except (TypeError, ValueError):
            return error("validation_error", "amount_cents 必须是整数", 400)
    for field in ("currency", "assumptions", "exclusions", "payment_terms"):
        if field in data:
            setattr(quote, field, data[field])
    if "items" in data:
        quote.items_json = data["items"] or []
    record_audit(
        "quote_updated",
        object_type="quote",
        object_id=quote.id,
        project_id=db.session.get(RFP, quote.rfp_id).project_id,
    )
    db.session.commit()
    return jsonify({"data": {"id": quote.id, "amount_cents": quote.amount_cents}})


@api_bp.get("/projects/<project_id>/quote-comparison")
@roles_required("pm", "admin")
def quote_comparison(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    rows = (
        db.session.query(Quote, RFP, Provider, Task)
        .join(RFP, Quote.rfp_id == RFP.id)
        .join(Provider, Quote.provider_id == Provider.id)
        .join(Task, Quote.task_id == Task.id)
        .filter(RFP.project_id == project.id)
        .order_by(Task.code.asc(), Quote.amount_cents.asc())
        .all()
    )
    grouped = {}
    for quote, rfp, provider, task in rows:
        bucket = grouped.setdefault(
            task.code,
            {
                "task_id": task.id,
                "task_code": task.code,
                "task_name": task.name,
                "quotes": [],
            },
        )
        bucket["quotes"].append(
            {
                "id": quote.id,
                "provider_name": provider.name,
                "provider_type": provider.type,
                "currency": quote.currency,
                "amount_cents": quote.amount_cents,
                "items": quote.items_json,
                "assumptions": quote.assumptions,
                "exclusions": quote.exclusions,
                "payment_terms": quote.payment_terms,
                "rfp_id": rfp.id,
            }
        )

    for bucket in grouped.values():
        amounts = [quote["amount_cents"] for quote in bucket["quotes"]]
        lowest = min(amounts) if amounts else 0
        highest = max(amounts) if amounts else 0
        bucket["lowest_amount_cents"] = lowest
        bucket["spread_percent"] = (
            round((highest - lowest) / lowest * 100, 2) if lowest else 0
        )
        for quote in bucket["quotes"]:
            quote["is_lowest"] = quote["amount_cents"] == lowest

    return jsonify(
        {
            "data": {
                "tasks": list(grouped.values()),
                "provider_amount_cents": provider_amount_for_project(project.id),
            }
        }
    )


def _client_quote_payload(row):
    fee_percent = (
        round(row.management_fee_cents / row.total_cents * 100, 2)
        if row.total_cents
        else 0
    )
    return {
        "id": row.id,
        "version": row.version,
        "provider_amount_cents": row.provider_amount_cents,
        "lawyer_amount_cents": row.lawyer_amount_cents,
        "management_fee_rate": row.management_fee_rate,
        "management_fee_cents": row.management_fee_cents,
        "total_cents": row.total_cents,
        "currency": row.currency,
        "status": row.status,
        "fee_percent": fee_percent,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "created_at": row.created_at.isoformat(),
    }


@api_bp.post("/projects/<project_id>/client-quotes")
@roles_required("pm", "admin")
def create_client_quote(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    provider_amount = data.get("provider_amount_cents")
    if provider_amount in (None, ""):
        provider_amount = provider_amount_for_project(project.id)
    try:
        provider_amount = int(provider_amount)
        lawyer_amount = int(data.get("lawyer_amount_cents") or 0)
    except (TypeError, ValueError):
        return error("validation_error", "金额必须是整数分", 400)
    if provider_amount <= 0:
        return error("validation_error", "服务商费用必须大于 0", 400)

    rate = data.get("management_fee_rate")
    if rate in (None, ""):
        rate = current_app.config["MANAGEMENT_FEE_RATE"]
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return error("validation_error", "管理费率必须是数字", 400)
    if rate > 1 and rate <= 100:
        rate = rate / 100
    if rate < 0 or rate > 1:
        return error("validation_error", "管理费率必须在 0 到 1 之间", 400)

    fee = int(round(provider_amount * rate))
    total = provider_amount + lawyer_amount + fee
    latest = (
        ClientQuote.query.filter_by(project_id=project.id)
        .order_by(ClientQuote.version.desc())
        .first()
    )
    row = ClientQuote(
        project_id=project.id,
        version=(latest.version if latest else 0) + 1,
        provider_amount_cents=provider_amount,
        lawyer_amount_cents=lawyer_amount,
        management_fee_rate=rate,
        management_fee_cents=fee,
        total_cents=total,
        currency=str(data.get("currency", "CNY")).upper(),
        status="draft",
    )
    db.session.add(row)
    db.session.flush()
    fire_project(project, "client_quote_created")
    project.total_quote_json = _client_quote_payload(row)
    record_audit(
        "client_quote_created",
        object_type="client_quote",
        object_id=row.id,
        project_id=project.id,
        detail={"version": row.version, "total_cents": total},
    )
    db.session.commit()
    return jsonify({"data": _client_quote_payload(row)}), 201


@api_bp.get("/projects/<project_id>/client-quotes")
@roles_required("pm", "admin")
def list_client_quotes(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    rows = (
        ClientQuote.query.filter_by(project_id=project.id)
        .order_by(ClientQuote.version.desc())
        .all()
    )
    return jsonify({"data": [_client_quote_payload(row) for row in rows]})


@api_bp.post("/client-quotes/<client_quote_id>/send")
@roles_required("pm", "admin")
def send_client_quote(client_quote_id):
    row = db.session.get(ClientQuote, client_quote_id)
    if row is None:
        return error("not_found", "总报价不存在", 404)
    from datetime import datetime

    fire_client_quote(row, "send")
    row.sent_at = datetime.utcnow()
    record_audit(
        "client_quote_sent",
        object_type="client_quote",
        object_id=row.id,
        project_id=row.project_id,
    )
    db.session.commit()
    return jsonify({"data": _client_quote_payload(row)})


@api_bp.get("/link/<token>/client-quote")
def link_client_quote(token):
    row, failure = _client_token(token)
    if failure:
        return failure
    quote = (
        ClientQuote.query.filter_by(project_id=row.project_id)
        .order_by(ClientQuote.version.desc())
        .first()
    )
    if quote is None:
        return error("not_found", "总报价尚未生成", 404)
    if quote.status not in {"sent", "confirmed"}:
        return error("conflict", "总报价尚未发送给客户", 409)
    return jsonify({"data": _client_quote_payload(quote)})


@api_bp.post("/link/<token>/client-quote/confirm")
def confirm_client_quote(token):
    row, failure = _client_token(token)
    if failure:
        return failure
    quote = (
        ClientQuote.query.filter_by(project_id=row.project_id)
        .order_by(ClientQuote.version.desc())
        .first()
    )
    if quote is None:
        return error("not_found", "总报价尚未生成", 404)
    if quote.status == "confirmed":
        return jsonify({"data": _client_quote_payload(quote)})
    if quote.status != "sent":
        return error("conflict", "当前状态不能确认", 409)

    from datetime import datetime

    fire_client_quote(quote, "confirm")
    quote.confirmed_at = datetime.utcnow()
    quote.confirm_ip = client_ip()
    project = db.session.get(Project, row.project_id)
    fire_project(project, "client_quote_confirmed")
    project.total_quote_json = _client_quote_payload(quote)
    record_audit(
        "client_quote_confirmed",
        object_type="client_quote",
        object_id=quote.id,
        project_id=row.project_id,
        actor_label=f"client:{row.subject_id or row.id}",
        detail={"version": quote.version},
    )
    db.session.commit()
    return jsonify({"data": _client_quote_payload(quote)})

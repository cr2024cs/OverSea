import argparse
import json
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

from app.config import PROJECT_ROOT
from app.extensions import db
from app.models import (
    AccessToken,
    Archive,
    AuditLog,
    Candidate,
    ClientQuote,
    ConfigItem,
    Contract,
    Conversation,
    Document,
    Fact,
    Finding,
    KnowledgeChunk,
    Message,
    Milestone,
    PerformanceEvent,
    Project,
    Proposal,
    Provider,
    QueryLetter,
    Quote,
    RFP,
    Task,
    TaskTemplate,
    User,
)
from app.seeds.base_data import CONFIG_ITEMS, PROVIDERS, USERS
from app.seeds.demo_data import (
    DEMO_COMPLETED_PROJECT_NAME,
    DEMO_DOCUMENTS,
    DEMO_FACTS,
    DEMO_PROJECT,
    DEMO_PROJECT_NAME,
    DEMO_QUOTE_ITEMS,
    DEMO_RFP_EN,
    DEMO_RFP_ZH,
    DEMO_TOTAL_QUOTE,
)
from app.seeds.findings_data import DEMO_FINDINGS
from app.seeds.knowledge import load_documents
from app.seeds.task_data import TASK_TEMPLATES


def _as_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def ensure_config():
    for item in CONFIG_ITEMS:
        row = ConfigItem.query.filter_by(type=item["type"], code=item["code"]).first()
        if row is None:
            row = ConfigItem(type=item["type"], code=item["code"])
            db.session.add(row)
        row.name = item["name"]
        row.enabled = item["enabled"]
        row.sort = item["sort"]
        row.extra_json = item.get("extra", {})


def ensure_users():
    for item in USERS:
        row = User.query.filter_by(email=item["email"]).first()
        if row is None:
            row = User(
                email=item["email"],
                password_hash=generate_password_hash(item["password"]),
            )
            db.session.add(row)
        row.name = item["name"]
        row.company = item.get("company")
        row.role = item["role"]
        row.active = True


def ensure_providers():
    for item in PROVIDERS:
        row = Provider.query.filter_by(name=item["name"]).first()
        if row is None:
            row = Provider(name=item["name"])
            db.session.add(row)
        row.type = item["type"]
        row.country = "Thailand"
        row.city = item["city"]
        row.description = item["description"]
        row.qualification = item["qualification"]
        row.evidence_level = item["evidence_level"]
        row.source_type = item["source_type"]
        row.contact_name = item["contact_name"]
        row.contact_email = item["contact_email"]


def link_provider_user():
    user = User.query.filter_by(email="provider@demo.local").first()
    provider = Provider.query.filter_by(name="曼谷商法律师事务所").first()
    if user is not None and provider is not None:
        user.provider_id = provider.id


def ensure_templates():
    for item in TASK_TEMPLATES:
        row = TaskTemplate.query.filter_by(code=item["code"]).first()
        if row is None:
            row = TaskTemplate(code=item["code"])
            db.session.add(row)
        row.name = item["name"]
        row.country = "TH"
        row.industry = "manufacturing"
        row.entry_mode = "greenfield"
        row.category = item["category"]
        row.provider_type = item["provider_type"]
        row.stage_no = item["stage_no"]
        row.trigger_condition = item["trigger_condition"]
        row.required_info_json = item["required_info"]
        row.deliverables_json = item["deliverables"]
        row.duration_days = item["duration_days"]
        row.fee_min_cents = item["fee_min_cents"]
        row.fee_max_cents = item["fee_max_cents"]
        row.predecessor_codes_json = item["predecessors"]
        row.qualification = item["qualification"]
        row.review_checklist_json = item["review_checklist"]
        row.legal_basis = item["legal_basis"]
        row.effective_date = _as_date(item["effective_date"])
        row.last_reviewed = _as_date(item["last_reviewed"])
        row.reviewer = item["reviewer"]
        row.is_critical = item["is_critical"]
        row.enabled = True


def seed_knowledge():
    KnowledgeChunk.query.delete()
    documents = load_documents(PROJECT_ROOT / "rag")
    for doc in documents:
        for chunk in doc["chunks"]:
            db.session.add(
                KnowledgeChunk(
                    doc_code=doc["doc_code"],
                    title=doc["title"],
                    country=doc["country"],
                    industry=doc["industry"],
                    topic=doc["topic"],
                    source_priority=doc["source_priority"],
                    last_reviewed=doc["last_reviewed"],
                    seq=chunk["seq"],
                    heading_path=chunk["heading_path"],
                    content=chunk["content"],
                    char_start=chunk["char_start"],
                    char_end=chunk["char_end"],
                )
            )
    return len(documents)


def _delete_project_data(project_id: str):
    for archive in Archive.query.filter_by(project_id=project_id).all():
        try:
            Path(archive.zip_path).unlink(missing_ok=True)
        except OSError:
            pass
    Archive.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Message.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Conversation.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Candidate.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    ClientQuote.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    PerformanceEvent.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    rfp_ids = [row.id for row in RFP.query.filter_by(project_id=project_id).all()]
    if rfp_ids:
        Quote.query.filter(Quote.rfp_id.in_(rfp_ids)).delete(synchronize_session=False)
    Finding.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    QueryLetter.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Milestone.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Contract.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    RFP.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Proposal.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Fact.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Document.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    Task.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    AccessToken.query.filter_by(project_id=project_id).delete(synchronize_session=False)
    AuditLog.query.filter_by(project_id=project_id).delete(synchronize_session=False)


def delete_demo_project():
    project = Project.query.filter_by(name=DEMO_PROJECT_NAME).first()
    if project is None:
        return False
    _delete_project_data(project.id)
    db.session.delete(project)
    db.session.flush()
    return True


def ensure_demo_project():
    existing = Project.query.filter_by(name=DEMO_PROJECT_NAME).first()
    if existing is not None:
        client_user = User.query.filter_by(email="client@demo.local").first()
        if client_user is not None and not existing.client_user_id:
            existing.client_user_id = client_user.id
        return False

    project = Project(**DEMO_PROJECT)
    client_user = User.query.filter_by(email="client@demo.local").first()
    if client_user is not None:
        project.client_user_id = client_user.id
    db.session.add(project)
    db.session.flush()

    docs = {}
    for item in DEMO_DOCUMENTS:
        doc = Document(
            project_id=project.id,
            filename=item["filename"],
            mime=item["mime"],
            text_content=item["text"],
            page_texts_json=[item["text"]],
            page_count=1,
            size_bytes=len(item["text"].encode("utf-8")),
        )
        db.session.add(doc)
        db.session.flush()
        docs[item["key"]] = doc

    for item in DEMO_FACTS:
        doc = docs.get(item["doc_key"])
        text = doc.text_content if doc else ""
        start = text.find(item["quote"])
        end = start + len(item["quote"]) if start >= 0 else None
        db.session.add(
            Fact(
                project_id=project.id,
                key=item["key"],
                value=item["value"],
                status=item["status"],
                doc_id=doc.id if doc else None,
                page=1 if doc else None,
                char_start=start if start >= 0 else None,
                char_end=end,
                quote=item["quote"],
                citation_status="verified",
            )
        )

    templates = TaskTemplate.query.filter_by(enabled=True).order_by(TaskTemplate.stage_no).all()
    task_by_code = {}
    for template in templates:
        task = Task(
            project_id=project.id,
            template_id=template.id,
            code=template.code,
            name=template.name,
            stage_no=template.stage_no,
            category=template.category,
            status="pending",
            is_critical=template.is_critical,
            locked=bool(template.predecessor_codes_json),
            due_date=date.today() + timedelta(days=template.duration_days),
            duration_days=template.duration_days,
            acceptance_criteria="；".join(template.review_checklist_json),
            deliverables_json=template.deliverables_json,
            predecessor_codes_json=template.predecessor_codes_json,
        )
        db.session.add(task)
        db.session.flush()
        task_by_code[task.code] = task

    for item in DEMO_FINDINGS:
        db.session.add(
            Finding(
                project_id=project.id,
                category=item["category"],
                severity=item["severity"],
                conclusion_level=item["conclusion_level"],
                quote_text=item["quote_text"],
                reason=item["reason"],
                question_zh=item["question_zh"],
                question_en=item["question_en"],
                is_legal=item["is_legal"],
                sources_json=item["sources_json"],
                citation_status=item.get("citation_status", "verified"),
                reviewer_status="pending",
            )
        )

    provider = Provider.query.filter_by(name="曼谷商法律师事务所").first()
    if provider and "T11" in task_by_code:
        rfp = RFP(
            project_id=project.id,
            task_id=task_by_code["T11"].id,
            provider_id=provider.id,
            version=1,
            content_zh=DEMO_RFP_ZH,
            content_en=DEMO_RFP_EN,
            status="sent",
            token=secrets.token_urlsafe(48),
            sent_at=datetime.utcnow(),
        )
        db.session.add(rfp)
        db.session.flush()
        db.session.add(
            Quote(
                rfp_id=rfp.id,
                provider_id=provider.id,
                task_id=task_by_code["T11"].id,
                currency="CNY",
                amount_cents=40_000_000,
                items_json=DEMO_QUOTE_ITEMS,
                assumptions="假设客户提供完整工艺说明与设备清单；不含 BOI 规费与差旅。",
                exclusions="不含工厂建设、设备采购与本地环评费用。",
                payment_terms="签约 50%，取证 50%。",
                raw_text="BOI 服务报价合计人民币 40 万元（演示）。",
                status="received",
            )
        )

    project.total_quote_json = DEMO_TOTAL_QUOTE
    return True


def delete_completed_demo_project():
    project = Project.query.filter_by(name=DEMO_COMPLETED_PROJECT_NAME).first()
    if project is None:
        return False
    _delete_project_data(project.id)
    db.session.delete(project)
    db.session.flush()
    return True


def _completed_proposal_content(total_cents):
    chapters = [
        ("项目背景与目标", "客户计划在泰国东部经济走廊设立汽车零部件工厂，投资约 3,000 万美元，目标第 14 个月试产。"),
        ("投资架构与持股", "由中国母公司 100% 持股，并按需评估香港中间层，兼顾税负、融资与退出。"),
        ("选址与土地厂房", "优先 IEAT 工业园区，已完成土地尽调、租赁登记、建筑许可与竣工验收。"),
        ("BOI 投资优惠", "已取得 BOI 投资优惠证书，覆盖企业所得税减免、机器进口关税减免与外资持股。"),
        ("公司设立与合规", "泰国公司完成注册、税务登记、外商经营证书与银行开户，注资与 ODI 备案一致。"),
        ("设备跨境转移", "国内二手设备完成评估、出口管制核查、BOI 机器清单审批与进口免税放行。"),
        ("用工与派驻", "完成泰籍员工招聘、工作规章备案，以及中方人员 BOI 外籍岗位与工作许可。"),
        ("预算与履约计划", "实际结算与计划基本一致，关键路径按节点表完成，已通过验收并归档。"),
    ]
    return {
        "title": "泰国春武里汽车零部件工厂项目建议书（完结版）",
        "chapters": [
            {"id": index + 1, "title": title, "content": body}
            for index, (title, body) in enumerate(chapters)
        ],
        "budget": {
            "low_cents": int(total_cents * 0.95),
            "mid_cents": total_cents,
            "high_cents": int(total_cents * 1.08),
            "basis": "已完成项目实际结算",
            "disclaimer": "本预算为演示数据，不构成正式报价。",
        },
        "references": [],
    }


def ensure_completed_demo_project():
    existing = Project.query.filter_by(name=DEMO_COMPLETED_PROJECT_NAME).first()
    if existing is not None:
        return False

    now = datetime.utcnow()
    client_user = User.query.filter_by(email="client@demo.local").first()
    pm_user = User.query.filter_by(email="pm@demo.local").first()
    lawyer_user = User.query.filter_by(email="lawyer@demo.local").first()
    expert_user = User.query.filter_by(email="expert@demo.local").first()

    project = Project(
        name=DEMO_COMPLETED_PROJECT_NAME,
        client_name=DEMO_PROJECT["client_name"],
        contact_name=DEMO_PROJECT["contact_name"],
        contact_email=DEMO_PROJECT["contact_email"],
        contact_phone=DEMO_PROJECT["contact_phone"],
        country="TH",
        industry="manufacturing",
        entry_mode="greenfield",
        goal_text=DEMO_PROJECT["goal_text"],
        investment_cents=DEMO_PROJECT["investment_cents"],
        currency="USD",
        phase=7,
        status="closed",
        archived=True,
        archived_at=now,
        requirement_confirmed_at=now,
        created_by=pm_user.id if pm_user else None,
        task_graph_snapshot_json={
            "total_days": 420,
            "critical_path": ["T14", "T16", "T17", "T18", "T29"],
        },
    )
    if client_user is not None:
        project.client_user_id = client_user.id
    db.session.add(project)
    db.session.flush()

    conversation = Conversation(
        project_id=project.id,
        title="完结版项目对话",
        created_by=client_user.id if client_user else None,
    )
    db.session.add(conversation)
    db.session.flush()
    db.session.add(
        Message(
            conversation_id=conversation.id,
            project_id=project.id,
            role="user",
            content="我们计划在泰国东部经济走廊设厂，投资约 3000 万美元，目标 14 个月试产。",
        )
    )
    db.session.add(
        Message(
            conversation_id=conversation.id,
            project_id=project.id,
            role="assistant",
            content="项目已完成调研、建议、询价、报价、签约、履约与归档七个阶段，可在工作台查看各阶段交付。",
        )
    )

    docs = {}
    for item in DEMO_DOCUMENTS:
        doc = Document(
            project_id=project.id,
            filename=item["filename"],
            mime=item["mime"],
            text_content=item["text"],
            page_texts_json=[item["text"]],
            page_count=1,
            size_bytes=len(item["text"].encode("utf-8")),
        )
        db.session.add(doc)
        db.session.flush()
        docs[item["key"]] = doc

    for item in DEMO_FACTS:
        doc = docs.get(item["doc_key"])
        text = doc.text_content if doc else ""
        start = text.find(item["quote"])
        end = start + len(item["quote"]) if start >= 0 else None
        db.session.add(
            Fact(
                project_id=project.id,
                key=item["key"],
                value=item["value"],
                status=item["status"],
                doc_id=doc.id if doc else None,
                page=1 if doc else None,
                char_start=start if start >= 0 else None,
                char_end=end,
                quote=item["quote"],
                citation_status="verified",
            )
        )

    templates = (
        TaskTemplate.query.filter_by(enabled=True)
        .order_by(TaskTemplate.stage_no, TaskTemplate.code)
        .all()
    )
    template_by_code = {template.code: template for template in templates}
    task_by_code = {}
    for template in templates:
        task = Task(
            project_id=project.id,
            template_id=template.id,
            code=template.code,
            name=template.name,
            stage_no=template.stage_no,
            category=template.category,
            status="done",
            is_critical=template.is_critical,
            locked=False,
            due_date=date.today() - timedelta(days=30),
            duration_days=template.duration_days,
            acceptance_criteria="；".join(template.review_checklist_json or []),
            deliverables_json=template.deliverables_json,
            predecessor_codes_json=template.predecessor_codes_json,
        )
        db.session.add(task)
        db.session.flush()
        task_by_code[task.code] = task

    project.selected_services_json = {
        "codes": [template.code for template in templates],
        "source": "client",
        "override_reason": None,
        "updated_at": now.isoformat(),
    }
    project.requirement_json = {
        "title": "需求确认书（完结版）",
        "project_name": project.name,
        "client_name": project.client_name,
        "scope_statement": (
            "客户委托平台完成泰国春武里汽车零部件工厂从投资调研、BOI、公司设立、"
            "土地厂房、设备转移到投产合规的全流程服务。"
        ),
        "task_summary": {
            "total": len(templates),
            "total_days": 420,
            "critical_path": ["T14", "T16", "T17", "T18", "T29"],
        },
        "confirmed_at": now.isoformat(),
        "disclaimer": "本确认书为演示数据，不构成正式法律或投资意见。",
    }

    providers = Provider.query.all()
    provider_by_type = {}
    for provider in providers:
        provider_by_type.setdefault(provider.type, provider)
    fallback_provider = providers[0] if providers else None

    for index, template in enumerate(templates):
        task = task_by_code[template.code]
        chosen = []
        matched = provider_by_type.get(template.provider_type)
        if matched is not None:
            chosen.append(matched)
        for provider in providers:
            if len(chosen) >= 3:
                break
            if provider not in chosen:
                chosen.append(provider)
        for offset, provider in enumerate(chosen):
            db.session.add(
                Candidate(
                    project_id=project.id,
                    task_id=task.id,
                    provider_id=provider.id,
                    match_score=95 - offset * 5,
                    reason=f"类型匹配（{provider.type}）；{provider.evidence_level}",
                    evidence_json={
                        "qualification": provider.qualification,
                        "city": provider.city,
                        "evidence_level": provider.evidence_level,
                    },
                    source_type=provider.source_type,
                    status="shortlisted",
                )
            )

    total_provider_cents = 0
    for index, template in enumerate(templates):
        task = task_by_code[template.code]
        provider = provider_by_type.get(template.provider_type) or fallback_provider
        if provider is None:
            continue
        amount = max(int(template.fee_min_cents or 0), 1_000_000)
        rfp = RFP(
            project_id=project.id,
            task_id=task.id,
            provider_id=provider.id,
            version=1,
            content_zh=f"询价书（完结版演示）\n任务：{template.code} {template.name}\n请提交分项报价、假设、不含项与付款条件。",
            content_en=f"Request for Proposal (completed demo)\nTask: {template.code} {template.name}",
            status="replied",
            token=secrets.token_urlsafe(48),
            sent_at=now - timedelta(days=120),
            opened_at=now - timedelta(days=119),
        )
        db.session.add(rfp)
        db.session.flush()
        db.session.add(
            Quote(
                rfp_id=rfp.id,
                provider_id=provider.id,
                task_id=task.id,
                currency="CNY",
                amount_cents=amount,
                items_json=[{"name": "服务费", "amount_cents": amount}],
                assumptions="假设客户提供完整资料并配合面谈。",
                exclusions="不含政府规费与差旅。",
                payment_terms="签约 50%，交付验收 50%。",
                raw_text="已完成服务，结算金额见分项。",
                status="received",
            )
        )
        total_provider_cents += amount

    rate = 0.175
    fee_cents = int(round(total_provider_cents * rate))
    total_cents = total_provider_cents + fee_cents
    client_quote = ClientQuote(
        project_id=project.id,
        version=1,
        provider_amount_cents=total_provider_cents,
        lawyer_amount_cents=0,
        management_fee_rate=rate,
        management_fee_cents=fee_cents,
        total_cents=total_cents,
        currency="CNY",
        status="confirmed",
        sent_at=now - timedelta(days=110),
        confirmed_at=now - timedelta(days=108),
    )
    db.session.add(client_quote)
    db.session.flush()
    project.total_quote_json = {
        "id": client_quote.id,
        "version": 1,
        "provider_amount_cents": client_quote.provider_amount_cents,
        "lawyer_amount_cents": 0,
        "management_fee_rate": rate,
        "management_fee_cents": fee_cents,
        "total_cents": total_cents,
        "currency": "CNY",
        "status": "confirmed",
        "fee_percent": round(fee_cents / total_cents * 100, 2) if total_cents else 0,
        "sent_at": client_quote.sent_at.isoformat(),
        "confirmed_at": client_quote.confirmed_at.isoformat(),
        "created_at": now.isoformat(),
    }

    db.session.add(
        Proposal(
            project_id=project.id,
            version=1,
            status="client_confirmed",
            content_json=_completed_proposal_content(total_cents),
            model="deepseek-v4.1-flash",
            pm_reviewed_by=pm_user.id if pm_user else None,
            pm_reviewed_at=now - timedelta(days=280),
            sent_at=now - timedelta(days=275),
            client_confirmed_at=now - timedelta(days=270),
        )
    )

    contract = Contract(
        project_id=project.id,
        version=1,
        type="master",
        scope_json={"tasks": [template.code for template in templates]},
        total_cents=total_cents,
        currency="CNY",
        terms_json={
            "sla": {"交付周期": "按节点表", "质询回复": "5 个工作日"},
            "disclaimer": "本委托确认单为演示数据，不构成正式合同。",
        },
        status="active",
        file_hash="demo-completed-contract-hash",
        pm_reviewed_by=pm_user.id if pm_user else None,
        pm_reviewed_at=now - timedelta(days=200),
        client_confirmed_at=now - timedelta(days=198),
        provider_confirmed_at=now - timedelta(days=197),
    )
    db.session.add(contract)
    db.session.flush()

    milestones = []
    for template in templates:
        task = task_by_code[template.code]
        provider = provider_by_type.get(template.provider_type) or fallback_provider
        milestone = Milestone(
            project_id=project.id,
            task_id=task.id,
            contract_id=contract.id,
            provider_id=provider.id if provider else None,
            expert_user_id=None,
            name=task.name,
            deliverable="；".join(template.deliverables_json or []),
            acceptance_criteria="；".join(template.review_checklist_json or []),
            due_date=date.today() - timedelta(days=10),
            status="passed",
            acceptor_type="expert",
            expert_name=expert_user.name if expert_user else "验收专家",
            expert_scores_json={
                "completeness": 95,
                "quality": 92,
                "executability": 90,
                "timeliness": 88,
            },
            expert_comment="交付完整，符合验收标准。",
            expert_total=92.1,
            rounds=1,
            submitted_at=now - timedelta(days=20),
            submission_note="交付物已提交，包含所需报告与证明文件。",
            pm_review_status="approved",
            pm_review_note="初审通过。",
            expert_submitted_at=now - timedelta(days=15),
            expert_locked=True,
            client_confirmed_at=now - timedelta(days=12),
        )
        db.session.add(milestone)
        db.session.flush()
        milestones.append(milestone)

    finding_ids = []
    for item in DEMO_FINDINGS:
        finding = Finding(
            project_id=project.id,
            milestone_id=milestones[0].id if milestones else None,
            category=item["category"],
            severity=item["severity"],
            conclusion_level=item["conclusion_level"],
            quote_text=item["quote_text"],
            reason=item["reason"],
            question_zh=item["question_zh"],
            question_en=item["question_en"],
            is_legal=item["is_legal"],
            sources_json=item["sources_json"],
            citation_status=item.get("citation_status", "verified"),
            reviewer_status="approved",
            reviewer_id=lawyer_user.id if lawyer_user else None,
            reviewed_at=now - timedelta(days=30),
            reply_text="服务商已补充说明并完成修正。",
            closed_at=now - timedelta(days=25),
        )
        db.session.add(finding)
        db.session.flush()
        finding_ids.append(finding.id)

    db.session.add(
        QueryLetter(
            project_id=project.id,
            provider_id=fallback_provider.id if fallback_provider else None,
            finding_ids_json=finding_ids,
            content="质询函（完结版演示）：请逐条回复审查发现并补充证据。",
            approval_status="approved",
            approved_by=lawyer_user.id if lawyer_user else None,
            approved_by_role="lawyer",
            approved_at=now - timedelta(days=35),
            status="closed",
            sent_at=now - timedelta(days=34),
            closed_at=now - timedelta(days=25),
        )
    )

    for milestone in milestones[:5]:
        if milestone.provider_id is None:
            continue
        db.session.add(
            PerformanceEvent(
                project_id=project.id,
                provider_id=milestone.provider_id,
                milestone_id=milestone.id,
                type="milestone_passed",
                dimension="delivery",
                value=1,
                note="节点按期通过验收。",
                occurred_at=now - timedelta(days=12),
            )
        )

    project.retrospective_json = {
        "timeline": [
            {
                "name": milestone.name,
                "status": milestone.status,
                "due_date": milestone.due_date.isoformat(),
                "rounds": milestone.rounds,
            }
            for milestone in milestones
        ],
        "budget": {
            "planned_cents": total_cents,
            "actual_cents": total_cents,
            "currency": "CNY",
            "variance_percent": 0,
        },
        "issues": {
            "total": len(DEMO_FINDINGS),
            "major": sum(1 for item in DEMO_FINDINGS if item["severity"] == "重大"),
            "closed": len(DEMO_FINDINGS),
            "major_open": 0,
            "categories": sorted({item["category"] for item in DEMO_FINDINGS}),
        },
        "provider_performance": {
            "events": min(len(milestones), 5),
            "average_expert_score": 92.1,
            "narrative": "服务商整体按期交付，验收评分稳定。",
        },
        "critical_path_variance": {
            "scheduled_days": 420,
            "narrative": "关键路径按计划完成，无重大延期。",
        },
        "generated_at": now.isoformat(),
        "model": "deepseek-v4.1-flash",
    }

    from app.services.archive import build_archive, create_archive_row

    zip_path, file_hash, manifest, retention_until = build_archive(project, 1)
    db.session.add(
        create_archive_row(
            project,
            1,
            zip_path,
            file_hash,
            manifest,
            retention_until,
            pm_user.id if pm_user else None,
        )
    )
    return True


def counts():
    return {
        "config_items": ConfigItem.query.count(),
        "users": User.query.count(),
        "providers": Provider.query.count(),
        "task_templates": TaskTemplate.query.count(),
        "knowledge_chunks": KnowledgeChunk.query.count(),
        "projects": Project.query.count(),
        "tasks": Task.query.count(),
        "findings": Finding.query.count(),
        "rfps": RFP.query.count(),
        "quotes": Quote.query.count(),
        "documents": Document.query.count(),
        "facts": Fact.query.count(),
    }


def seed_all(reset_demo=False):
    ensure_config()
    ensure_users()
    ensure_providers()
    link_provider_user()
    ensure_templates()
    knowledge_docs = seed_knowledge()

    if reset_demo:
        delete_demo_project()
        delete_completed_demo_project()
    ensure_demo_project()
    ensure_completed_demo_project()
    db.session.commit()

    result = counts()
    result["knowledge_documents"] = knowledge_docs
    return result


def main():
    parser = argparse.ArgumentParser(description="Seed the Oversea MVP database.")
    parser.add_argument("--reset-demo", action="store_true", help="Reset the demo project.")
    parser.add_argument("--drop", action="store_true", help="Drop all tables before seeding.")
    args = parser.parse_args()

    from app import create_app

    app = create_app()
    with app.app_context():
        if args.drop:
            db.drop_all()
            db.create_all()
        result = seed_all(reset_demo=args.reset_demo)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

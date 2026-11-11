from datetime import date, datetime, timedelta

from flask import g, jsonify, request

from app.ai.provider import AIProvider
from app.api import api_bp
from app.api.deps import login_required, roles_required
from app.api.errors import error
from app.extensions import db
from app.models import Conversation, Document, Fact, Message, Project, Task, TaskTemplate
from app.services.audit import record_audit
from app.services.citation import locate_quote, verify_quote
from app.services.permissions import can_access_project
from app.services.state_machine import fire_project
from app.services.task_graph import (
    build_edges,
    compute_schedule,
    diff_snapshots,
    snapshot,
)
from app.services.tokens import resolve_access_token
from app.utils import client_ip

UNKNOWN_ANSWERS = {"不知道", "待确认", "不确定", "unknown", "n/a"}


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    if not can_access_project(g.current_user, project):
        return None, error("forbidden", "无权访问该项目", 403)
    return project, None


def _fact_payload(fact):
    document = db.session.get(Document, fact.doc_id) if fact.doc_id else None
    return {
        "id": fact.id,
        "key": fact.key,
        "value": fact.value,
        "status": fact.status,
        "quote": fact.quote,
        "citation_status": fact.citation_status,
        "citation": {
            "doc_id": document.id,
            "filename": document.filename,
            "char_start": fact.char_start,
            "char_end": fact.char_end,
        }
        if document
        else None,
    }


def _upsert_fact(project_id, key, value, status, document=None, quote=None):
    fact = Fact.query.filter_by(project_id=project_id, key=key).first()
    if fact is None:
        fact = Fact(project_id=project_id, key=key)
        db.session.add(fact)
    else:
        fact.version = (fact.version or 1) + 1

    fact.value = value
    fact.status = status
    fact.doc_id = document.id if document else None
    fact.page = 1 if document else None
    fact.quote = quote

    citation_status = "unverified"
    start = end = None
    if document and quote and verify_quote(quote, document.text_content or ""):
        citation_status = "verified"
        start, end = locate_quote(quote, document.text_content or "")
    fact.citation_status = citation_status
    fact.char_start = start
    fact.char_end = end
    return fact


@api_bp.post("/projects/<project_id>/facts/extract")
@roles_required("pm", "admin")
def extract_facts(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    documents = Document.query.filter_by(project_id=project.id).all()
    if not documents:
        return error("validation_error", "请先上传项目资料", 400)

    provider = AIProvider()
    outcome = provider.run(
        "extract_facts",
        {
            "project_id": project.id,
            "documents": [
                {
                    "filename": document.filename,
                    "text": (document.text_content or "")[:4000],
                }
                for document in documents
            ],
        },
    )
    fixture_facts = outcome["result"].get("facts", [])
    document_by_name = {document.filename: document for document in documents}

    verified_count = 0
    for item in fixture_facts:
        document = document_by_name.get(item.get("source_doc"))
        quote = item.get("quote")
        if document is None or not verify_quote(quote or "", document.text_content or ""):
            document = None
            for candidate in documents:
                if verify_quote(quote or "", candidate.text_content or ""):
                    document = candidate
                    break

        fact = _upsert_fact(
            project.id,
            item.get("key", "未命名事实"),
            item.get("value", ""),
            item.get("status", "unknown"),
            document=document,
            quote=quote,
        )
        if fact.citation_status == "verified":
            verified_count += 1

    record_audit(
        "ai_call",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        detail={
            "step": "extract_facts",
            "model": outcome["model"],
            "duration_ms": outcome["duration_ms"],
        },
    )
    db.session.commit()

    facts = Fact.query.filter_by(project_id=project.id).order_by(Fact.created_at.asc()).all()
    return jsonify(
        {
            "data": {
                "facts": [_fact_payload(fact) for fact in facts],
                "verified": verified_count,
                "unverified": len(facts) - verified_count,
            }
        }
    )


@api_bp.post("/projects/<project_id>/interview")
@roles_required("pm", "admin")
def generate_interview(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    conversation_id = data.get("conversation_id")
    conversation = None
    round_no = 1
    if conversation_id:
        conversation = db.session.get(Conversation, conversation_id)
        if conversation is None or conversation.project_id != project.id:
            return error("not_found", "对话不存在", 404)
        previous_rounds = Message.query.filter_by(
            conversation_id=conversation.id, intent="interview_questions"
        ).count()
        if previous_rounds >= 3:
            return error("round_limit", "最多支持 3 轮访谈", 400)
        round_no = previous_rounds + 1

    facts = Fact.query.filter_by(project_id=project.id).all()
    tasks = Task.query.filter_by(project_id=project.id).all()
    questionnaire = project.questionnaire_json or {}
    provider = AIProvider()
    outcome = provider.run(
        "interview",
        {
            "project_id": project.id,
            "facts": [{"key": fact.key, "value": fact.value} for fact in facts],
            "tasks": [task.code for task in tasks],
            "questionnaire": {
                "summary": questionnaire.get("summary", []),
                "followups": questionnaire.get("followups", []),
                "flags": questionnaire.get("flags", []),
            },
        },
    )
    questions = sorted(
        outcome["result"].get("questions", []), key=lambda item: item.get("priority", 99)
    )[:5]

    content = "\n".join(
        f"{index}. {item['text']}（影响：{', '.join(item.get('impact_tasks', []))}）"
        for index, item in enumerate(questions, start=1)
    )
    if conversation is not None:
        db.session.add(
            Message(
                conversation_id=conversation.id,
                project_id=project.id,
                role="assistant",
                content=content,
                intent="interview_questions",
                model=outcome["model"],
                cached=False,
            )
        )
        conversation.updated_at = datetime.utcnow()

    record_audit(
        "ai_call",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        detail={
            "step": "interview",
            "model": outcome["model"],
            "duration_ms": outcome["duration_ms"],
        },
    )
    db.session.commit()

    return jsonify({"data": {"round": round_no, "questions": questions}})


@api_bp.post("/projects/<project_id>/interview/answers")
@roles_required("pm", "admin")
def answer_interview(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or []
    if not answers:
        return error("validation_error", "answers 不能为空", 400)

    created = []
    for item in answers:
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not question:
            continue
        status = "unknown" if answer.lower() in UNKNOWN_ANSWERS else "assumption"
        fact = _upsert_fact(project.id, question, answer, status)
        created.append(fact)

    db.session.commit()
    return jsonify({"data": [_fact_payload(fact) for fact in created]})


def _task_payload(task):
    return {
        "id": task.id,
        "code": task.code,
        "name": task.name,
        "stage_no": task.stage_no,
        "status": task.status,
        "is_critical": task.is_critical,
        "is_external": task.is_external,
        "locked": task.locked,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "duration_days": task.duration_days,
        "predecessors": task.predecessor_codes_json or [],
        "deliverables": task.deliverables_json or [],
    }


def _graph_payload(project):
    tasks = (
        Task.query.filter_by(project_id=project.id)
        .order_by(Task.stage_no.asc(), Task.code.asc())
        .all()
    )
    task_dicts = [
        {
            "code": task.code,
            "name": task.name,
            "duration_days": task.duration_days,
            "predecessors": task.predecessor_codes_json or [],
        }
        for task in tasks
    ]
    graph_snapshot = project.task_graph_snapshot_json or {}
    if graph_snapshot.get("critical_path"):
        critical_path = graph_snapshot["critical_path"]
        total_days = graph_snapshot.get("total_days", 0)
    else:
        schedule = compute_schedule(task_dicts) if task_dicts else {
            "critical_path": [],
            "total_days": 0,
        }
        critical_path = schedule["critical_path"]
        total_days = schedule["total_days"]

    return {
        "tasks": [_task_payload(task) for task in tasks],
        "edges": build_edges(task_dicts),
        "critical_path": critical_path,
        "total_days": total_days,
        "scenario": graph_snapshot.get("scenario", "lease"),
        "generated_at": graph_snapshot.get("generated_at"),
        "diff": graph_snapshot.get("last_diff", {"first_generation": True}),
    }


@api_bp.post("/projects/<project_id>/tasks/refresh")
@roles_required("pm", "admin")
def refresh_tasks(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    scenario = data.get("scenario", "lease")
    if scenario not in {"lease", "land_purchase"}:
        return error("validation_error", "scenario 必须是 lease 或 land_purchase", 400)

    all_templates = TaskTemplate.query.filter_by(enabled=True).order_by(TaskTemplate.stage_no).all()
    if not all_templates:
        return error("validation_error", "任务模板为空", 400)

    questionnaire = project.questionnaire_json or {}
    selected_codes = set(questionnaire.get("selected_task_codes") or [])
    templates = (
        [item for item in all_templates if item.code in selected_codes]
        if selected_codes
        else all_templates
    )
    template_by_code = {template.code: template for template in all_templates}
    task_dicts = []
    for template in templates:
        predecessors = list(template.predecessor_codes_json or [])
        if scenario == "land_purchase" and template.code == "T14" and "T11" not in predecessors:
            predecessors.append("T11")
        task_dicts.append(
            {
                "code": template.code,
                "name": template.name,
                "stage_no": template.stage_no,
                "duration_days": template.duration_days,
                "predecessors": predecessors,
                "deliverables": template.deliverables_json or [],
                "review_checklist": template.review_checklist_json or [],
                "is_external": False,
                "template_id": template.id,
            }
        )

    extra_tasks = list(data.get("extra_tasks") or [])
    for index, item in enumerate(questionnaire.get("custom_tasks", []), start=1):
        extra_tasks.append(
            {
                "code": item.get("code") or f"C{index:02d}",
                "name": item.get("name") or "自定义任务",
                "stage_no": 0,
                "duration_days": 30,
                "predecessors": [],
            }
        )
    for index, item in enumerate(questionnaire.get("subtasks", []), start=1):
        extra_tasks.append(
            {
                "code": f"S{index:02d}",
                "name": item.get("name") or "子任务",
                "stage_no": 0,
                "duration_days": 15,
                "predecessors": [item["parent"]] if item.get("parent") else [],
            }
        )
    for item in extra_tasks:
        code = str(item.get("code", "")).strip()
        if not code:
            return error("validation_error", "模板外任务缺少 code", 400)
        if any(task["code"] == code for task in task_dicts):
            return error("validation_error", f"任务编号重复：{code}", 400)
        duration = int(item.get("duration_days") or 30)
        task_dicts.append(
            {
                "code": code,
                "name": str(item.get("name") or f"模板外任务 {code}"),
                "stage_no": int(item.get("stage_no") or 0),
                "duration_days": duration,
                "predecessors": list(item.get("predecessors") or []),
                "deliverables": list(item.get("deliverables") or []),
                "review_checklist": [],
                "is_external": True,
                "template_id": None,
            }
        )

    try:
        schedule = compute_schedule(task_dicts)
    except ValueError as exc:
        return error("dependency_error", str(exc), 400)

    critical = set(schedule["critical_path"])
    start = date.today()
    existing = {task.code: task for task in Task.query.filter_by(project_id=project.id)}

    for item in task_dicts:
        task = existing.get(item["code"])
        if task is None:
            task = Task(project_id=project.id, code=item["code"], status="pending")
            db.session.add(task)
        task.template_id = item["template_id"]
        task.name = item["name"]
        task.stage_no = item["stage_no"]
        task.category = (
            template_by_code[item["code"]].category
            if item["code"] in template_by_code
            else "模板外"
        )
        task.duration_days = item["duration_days"]
        task.predecessor_codes_json = item["predecessors"]
        task.deliverables_json = item["deliverables"]
        task.acceptance_criteria = "；".join(item["review_checklist"])
        task.is_external = item["is_external"]
        task.locked = bool(item["predecessors"])
        task.is_critical = item["code"] in critical
        task.due_date = start + timedelta(
            days=schedule["earliest_start"][item["code"]] + item["duration_days"]
        )

    new_snapshot = snapshot(task_dicts, schedule["critical_path"])
    previous = project.task_graph_snapshot_json or {}
    diff = diff_snapshots(previous, new_snapshot)
    project.task_graph_snapshot_json = {
        **new_snapshot,
        "total_days": schedule["total_days"],
        "scenario": scenario,
        "generated_at": datetime.utcnow().isoformat(),
        "last_diff": diff,
    }
    fire_project(project, "task_map_generated")

    record_audit(
        "task_graph_generated",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        detail={"scenario": scenario, "tasks": len(task_dicts), "diff": diff},
    )
    db.session.commit()

    return jsonify({"data": _graph_payload(project)})


@api_bp.get("/projects/<project_id>/task-graph")
@login_required
def get_task_graph(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    return jsonify({"data": _graph_payload(project)})


def _requirement_payload(project):
    requirement = project.requirement_json or {}
    if not requirement:
        return None
    payload = dict(requirement)
    payload["confirmed_at"] = (
        project.requirement_confirmed_at.isoformat()
        if project.requirement_confirmed_at
        else None
    )
    return payload


@api_bp.post("/projects/<project_id>/requirement")
@roles_required("pm", "admin")
def generate_requirement(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    facts = Fact.query.filter_by(project_id=project.id).order_by(Fact.created_at.asc()).all()
    tasks = Task.query.filter_by(project_id=project.id).all()
    stages = {}
    for task in tasks:
        stages[str(task.stage_no)] = stages.get(str(task.stage_no), 0) + 1

    graph = _graph_payload(project)
    requirement = {
        "title": "需求确认书",
        "project_name": project.name,
        "client_name": project.client_name,
        "goal_text": project.goal_text,
        "facts": [
            {
                "key": fact.key,
                "value": fact.value,
                "status": fact.status,
                "quote": fact.quote,
                "citation_status": fact.citation_status,
            }
            for fact in facts
        ],
        "task_summary": {
            "total": len(tasks),
            "by_stage": stages,
            "critical_path": graph["critical_path"],
            "total_days": graph["total_days"],
        },
        "scope_statement": "客户确认上述事实基础、任务范围与关键路径；后续范围变更需走变更记录。",
        "disclaimer": "本确认书用于平台内部推进项目，不构成法律意见，也不代替正式资格审查。",
        "generated_at": datetime.utcnow().isoformat(),
    }
    project.requirement_json = requirement
    fire_project(project, "requirement_generated")
    record_audit(
        "requirement_generated",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        detail={"facts": len(facts), "tasks": len(tasks)},
    )
    db.session.commit()

    return jsonify({"data": _requirement_payload(project)})


@api_bp.get("/projects/<project_id>/requirement")
@login_required
def get_requirement(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    payload = _requirement_payload(project)
    if payload is None:
        return error("not_found", "需求确认书尚未生成", 404)
    return jsonify({"data": payload})


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
        return None, error("forbidden", "该链接不是客户确认链接", 403)
    return row, None


@api_bp.get("/link/<token>/requirement")
def link_requirement(token):
    row, failure = _client_token(token)
    if failure:
        return failure

    project = db.session.get(Project, row.project_id)
    if project is None:
        return error("not_found", "项目不存在", 404)
    payload = _requirement_payload(project)
    if payload is None:
        return error("not_found", "需求确认书尚未生成", 404)
    return jsonify({"data": payload})


@api_bp.post("/link/<token>/requirement/confirm")
def confirm_requirement(token):
    row, failure = _client_token(token)
    if failure:
        return failure

    project = db.session.get(Project, row.project_id)
    if project is None:
        return error("not_found", "项目不存在", 404)
    if not project.requirement_json:
        return error("not_found", "需求确认书尚未生成", 404)

    if project.requirement_confirmed_at is None:
        project.requirement_confirmed_at = datetime.utcnow()
        record_audit(
            "requirement_confirmed",
            object_type="project",
            object_id=project.id,
            project_id=project.id,
            actor_label=f"client:{row.subject_id or row.id}",
            detail={"role_type": row.role_type},
        )
        project.requirement_json = {
            **(project.requirement_json or {}),
            "confirmed_ip": client_ip(),
        }
        db.session.commit()

    return jsonify({"data": _requirement_payload(project)})

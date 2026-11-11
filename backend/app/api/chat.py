import json
import time
from datetime import datetime

from flask import Response, g, jsonify, request, stream_with_context

from app.ai.provider import AIProvider
from app.api import api_bp
from app.api.deps import login_required
from app.api.errors import error
from app.extensions import db
from app.models import (
    Conversation,
    Document,
    Fact,
    Finding,
    Message,
    Milestone,
    Project,
    Proposal,
    Provider,
    Quote,
    RFP,
    Task,
)
from app.services.audit import record_audit
from app.services.permissions import can_access_project

INTENT_RULES = [
    ("review", ("审查", "质询", "答复", "发现")),
    ("proposal", ("建议书", "方案书", "预算区间")),
    ("tasks", ("任务", "地图", "关键路径", "依赖")),
    ("acceptance", ("验收", "评分", "专家")),
    ("archive", ("归档", "复盘")),
    ("interview", ("访谈", "追问", "资料", "事实")),
]


def detect_intent(text, phase):
    normalized = (text or "").strip()
    for intent, keywords in INTENT_RULES:
        if any(keyword in normalized for keyword in keywords):
            return intent
    return "interview" if phase <= 1 else "default"


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    if not can_access_project(g.current_user, project):
        return None, error("forbidden", "无权访问该项目", 403)
    return project, None


def _conversation(conversation_id):
    conversation = db.session.get(Conversation, conversation_id)
    if conversation is None:
        return None, error("not_found", "对话不存在", 404)
    project = db.session.get(Project, conversation.project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    if not can_access_project(g.current_user, project):
        return None, error("forbidden", "无权访问该对话", 403)
    return conversation, None


def message_dict(message):
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "intent": message.intent,
        "citations": message.citations_json or [],
        "model": message.model,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


@api_bp.get("/projects/<project_id>/conversations")
@login_required
def list_conversations(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    rows = (
        Conversation.query.filter_by(project_id=project.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return jsonify(
        {
            "data": [
                {
                    "id": row.id,
                    "title": row.title,
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in rows
            ]
        }
    )


@api_bp.post("/projects/<project_id>/conversations")
@login_required
def create_conversation(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "新对话").strip()[:200] or "新对话"
    row = Conversation(project_id=project.id, title=title, created_by=g.current_user.id)
    db.session.add(row)
    db.session.commit()
    return jsonify({"data": {"id": row.id, "title": row.title}}), 201


@api_bp.get("/conversations/<conversation_id>/messages")
@login_required
def list_messages(conversation_id):
    conversation, failure = _conversation(conversation_id)
    if failure:
        return failure

    rows = (
        Message.query.filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return jsonify({"data": [message_dict(row) for row in rows]})


@api_bp.post("/chat")
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    conversation_id = str(data.get("conversation_id", "")).strip()
    text = str(data.get("message", "")).strip()
    if not conversation_id:
        return error("validation_error", "缺少 conversation_id", 400)
    if not text:
        return error("validation_error", "消息不能为空", 400)
    if len(text) > 4000:
        return error("validation_error", "单条消息不能超过 4000 字", 400)

    conversation, failure = _conversation(conversation_id)
    if failure:
        return failure
    project = db.session.get(Project, conversation.project_id)

    intent = detect_intent(text, project.phase)
    user_message = Message(
        conversation_id=conversation.id,
        project_id=project.id,
        role="user",
        content=text,
        intent=intent,
    )
    db.session.add(user_message)
    if conversation.title == "新对话":
        conversation.title = text[:24]
    conversation.updated_at = datetime.utcnow()
    db.session.commit()

    history = (
        Message.query.filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at.asc())
        .all()[-12:]
    )
    system_prompt = (
        "你是 AI 原生专业服务总包平台的助手。"
        f"当前项目：{project.name}，国家 {project.country}，阶段 {project.phase}，状态 {project.status}。"
        "只提问、指出矛盾、标注缺失，不给出法律结论。回答简洁，必要时给出下一步建议。"
    )
    questionnaire = project.questionnaire_json or {}
    if questionnaire.get("summary"):
        system_prompt += "\n\n项目问卷摘要：\n" + "\n".join(
            f"- {item['question']}：{item['answer']}"
            for item in questionnaire["summary"][:12]
        )
    if questionnaire.get("followups"):
        system_prompt += "\n\n问卷标记的待追问：\n" + "\n".join(
            f"- {item['question']}（{item['option_label']}）"
            for item in questionnaire["followups"][:10]
        )
    if questionnaire.get("flags"):
        system_prompt += "\n\n风险提示：\n" + "\n".join(
            f"- {item.get('text')}" for item in questionnaire["flags"][:6]
        )
    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": row.role, "content": row.content} for row in history
    ]

    provider = AIProvider()
    outcome = provider.run(
        "chat",
        {"intent": intent, "message": text, "project_id": project.id},
        messages=messages,
    )
    reply = outcome["text"] or "已收到。请继续说明下一步需求。"
    assistant = Message(
        conversation_id=conversation.id,
        project_id=project.id,
        role="assistant",
        content=reply,
        intent=intent,
        model=outcome["model"],
        cached=False,
    )
    db.session.add(assistant)
    record_audit(
        "ai_call",
        object_type="message",
        object_id=assistant.id,
        project_id=project.id,
        detail={
            "step": "chat",
            "intent": intent,
            "model": outcome["model"],
            "tokens": outcome["tokens"],
            "duration_ms": outcome["duration_ms"],
            "prompt_version": outcome["prompt_version"],
        },
    )
    db.session.commit()

    delay_ms = stream_delay()

    def generate():
        for index in range(0, len(reply), 8):
            chunk = reply[index : index + 8]
            yield "data: " + json.dumps({"delta": chunk}, ensure_ascii=False) + "\n\n"
            if delay_ms:
                time.sleep(delay_ms / 1000.0)
        yield "data: " + json.dumps(
            {
                "done": True,
                "message_id": assistant.id,
                "intent": intent,
                "model": outcome["model"],
            },
            ensure_ascii=False,
        ) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def stream_delay():
    from flask import current_app

    return current_app.config.get("AI_STREAM_DELAY_MS", 10)


@api_bp.get("/projects/<project_id>/artifacts")
@login_required
def artifacts(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    artifact_type = request.args.get("type", "facts")
    if artifact_type == "facts":
        rows = (
            Fact.query.filter_by(project_id=project.id)
            .order_by(Fact.created_at.asc())
            .all()
        )
        payload = []
        for row in rows:
            doc = db.session.get(Document, row.doc_id) if row.doc_id else None
            payload.append(
                {
                    "id": row.id,
                    "key": row.key,
                    "value": row.value,
                    "status": row.status,
                    "quote": row.quote,
                    "citation": {
                        "doc_id": doc.id,
                        "filename": doc.filename,
                        "char_start": row.char_start,
                        "char_end": row.char_end,
                    }
                    if doc
                    else None,
                }
            )
        return jsonify({"data": payload})

    if artifact_type == "tasks":
        rows = (
            Task.query.filter_by(project_id=project.id)
            .order_by(Task.stage_no.asc(), Task.code.asc())
            .all()
        )
        return jsonify(
            {
                "data": [
                    {
                        "id": row.id,
                        "code": row.code,
                        "name": row.name,
                        "stage_no": row.stage_no,
                        "status": row.status,
                        "is_critical": row.is_critical,
                        "locked": row.locked,
                        "due_date": row.due_date.isoformat() if row.due_date else None,
                        "deliverables": row.deliverables_json,
                    }
                    for row in rows
                ]
            }
        )

    if artifact_type == "proposal":
        row = (
            Proposal.query.filter_by(project_id=project.id)
            .order_by(Proposal.version.desc())
            .first()
        )
        return jsonify(
            {
                "data": {
                    "id": row.id,
                    "version": row.version,
                    "status": row.status,
                    "content": row.content_json,
                    "client_confirmed_at": row.client_confirmed_at.isoformat()
                    if row.client_confirmed_at
                    else None,
                }
                if row
                else None
            }
        )

    if artifact_type == "quotes":
        rows = (
            Quote.query.join(RFP, Quote.rfp_id == RFP.id)
            .filter(RFP.project_id == project.id)
            .order_by(Quote.created_at.desc())
            .all()
        )
        payload = []
        for row in rows:
            provider = db.session.get(Provider, row.provider_id)
            task = db.session.get(Task, row.task_id)
            payload.append(
                {
                    "id": row.id,
                    "provider": provider.name if provider else None,
                    "task_code": task.code if task else None,
                    "task_name": task.name if task else None,
                    "currency": row.currency,
                    "amount_cents": row.amount_cents,
                    "items": row.items_json,
                    "assumptions": row.assumptions,
                    "exclusions": row.exclusions,
                    "payment_terms": row.payment_terms,
                }
            )
        return jsonify(
            {"data": {"quotes": payload, "total": project.total_quote_json or {}}}
        )

    if artifact_type == "milestones":
        rows = (
            Milestone.query.filter_by(project_id=project.id)
            .order_by(Milestone.due_date.asc())
            .all()
        )
        return jsonify(
            {
                "data": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "status": row.status,
                        "due_date": row.due_date.isoformat() if row.due_date else None,
                        "acceptor_type": row.acceptor_type,
                        "rounds": row.rounds,
                    }
                    for row in rows
                ]
            }
        )

    if artifact_type == "findings":
        rows = (
            Finding.query.filter_by(project_id=project.id)
            .order_by(Finding.created_at.asc())
            .all()
        )
        return jsonify(
            {
                "data": [
                    {
                        "id": row.id,
                        "category": row.category,
                        "severity": row.severity,
                        "conclusion_level": row.conclusion_level,
                        "quote_text": row.quote_text,
                        "reason": row.reason,
                        "question_zh": row.question_zh,
                        "question_en": row.question_en,
                        "is_legal": row.is_legal,
                        "reviewer_status": row.reviewer_status,
                    }
                    for row in rows
                ]
            }
        )

    return error("validation_error", "不支持的产物类型", 400)


@api_bp.get("/documents/<document_id>")
@login_required
def get_document(document_id):
    document = db.session.get(Document, document_id)
    if document is None:
        return error("not_found", "文档不存在", 404)

    project = db.session.get(Project, document.project_id)
    if not can_access_project(g.current_user, project):
        return error("forbidden", "无权访问该文档", 403)

    return jsonify(
        {
            "data": {
                "id": document.id,
                "filename": document.filename,
                "text": document.text_content or "",
                "page_count": document.page_count,
            }
        }
    )

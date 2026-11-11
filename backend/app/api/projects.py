from flask import g, jsonify, request

from app.api import api_bp
from app.api.deps import login_required
from app.api.errors import error
from app.extensions import db
from app.models import ConfigItem, Conversation, Message, Project
from app.services.audit import record_audit
from app.services.permissions import can_access_project, is_internal
from app.services.questionnaire import evaluate
from app.services.state_machine import PHASE_LABELS, STATUS_LABELS


def project_summary(project):
    return {
        "id": project.id,
        "name": project.name,
        "client_name": project.client_name,
        "country": project.country,
        "industry": project.industry,
        "entry_mode": project.entry_mode,
        "phase": project.phase,
        "phase_label": PHASE_LABELS.get(project.phase, str(project.phase)),
        "status": project.status,
        "status_label": STATUS_LABELS.get(project.status, project.status),
        "archived": project.archived,
        "investment_cents": project.investment_cents,
        "currency": project.currency,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


def project_detail(project):
    data = project_summary(project)
    data.update(
        {
            "goal_text": project.goal_text,
            "investment_cents": project.investment_cents,
            "currency": project.currency,
            "contact_name": project.contact_name,
            "contact_email": project.contact_email,
            "contact_phone": project.contact_phone,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }
    )
    return data


def _enabled_config(item_type, code):
    return (
        ConfigItem.query.filter_by(type=item_type, code=code, enabled=True).first()
        is not None
    )


@api_bp.post("/projects")
@login_required
def create_project():
    data = request.get_json(silent=True) or {}
    user = g.current_user

    country = str(data.get("country", "")).strip()
    industry = str(data.get("industry", "")).strip()
    entry_mode = str(data.get("entry_mode", "")).strip()
    if not _enabled_config("country", country):
        return error("validation_error", "请选择已启用的国家", 400)
    if not _enabled_config("industry", industry):
        return error("validation_error", "请选择已启用的行业", 400)
    if not _enabled_config("entry_mode", entry_mode):
        return error("validation_error", "请选择已启用的出海方式", 400)

    if user.role == "client":
        client_name = user.company or user.name
    else:
        client_name = str(data.get("client_name", "")).strip()
        if not client_name:
            return error("validation_error", "请填写客户名称", 400)

    country_item = ConfigItem.query.filter_by(
        type="country", code=country
    ).first()
    name = str(data.get("name", "")).strip()
    if not name:
        name = f"{client_name} · {country_item.name if country_item else country}项目"

    investment_cents = data.get("investment_cents")
    if investment_cents in (None, ""):
        investment_cents = None
    else:
        try:
            investment_cents = int(investment_cents)
        except (TypeError, ValueError):
            return error("validation_error", "投资金额必须是整数分", 400)
        if investment_cents < 0:
            return error("validation_error", "投资金额不能为负", 400)

    currency = str(data.get("currency", "USD")).upper()
    if not _enabled_config("currency", currency):
        return error("validation_error", "请选择已启用的币种", 400)

    project = Project(
        name=name,
        client_name=client_name,
        contact_name=str(data.get("contact_name") or user.name),
        contact_email=str(data.get("contact_email") or user.email),
        contact_phone=str(data.get("contact_phone") or ""),
        country=country,
        industry=industry,
        entry_mode=entry_mode,
        goal_text=str(data.get("goal_text", "")).strip(),
        investment_cents=investment_cents,
        currency=currency,
        phase=1,
        status="draft",
        created_by=user.id,
        client_user_id=user.id if user.role == "client" else None,
    )

    questionnaire = data.get("questionnaire") or {}
    answers = questionnaire.get("answers") or {}
    if answers:
        project.questionnaire_json = evaluate(
            answers,
            {
                "country": country,
                "industry": industry,
                "entry_mode": entry_mode,
            },
        )
    db.session.add(project)
    db.session.flush()

    if project.questionnaire_json:
        payload = project.questionnaire_json
        summary_lines = [
            f"{item['question']}：{item['answer']}"
            for item in payload.get("summary", [])[:8]
        ]
        followup_lines = [
            f"{item['question']}（{item['option_label']}）"
            for item in payload.get("followups", [])
        ]
        content = "问卷已完成。"
        if summary_lines:
            content += "\n\n已记录：\n" + "\n".join(f"- {line}" for line in summary_lines)
        if followup_lines:
            content += "\n\n需要进一步确认：\n" + "\n".join(
                f"- {line}" for line in followup_lines
            )
        content += "\n\n可以继续补充项目目标，我会基于问卷继续提问。"

        conversation = Conversation(
            project_id=project.id,
            title="项目启动问卷",
            created_by=user.id,
        )
        db.session.add(conversation)
        db.session.flush()
        db.session.add(
            Message(
                conversation_id=conversation.id,
                project_id=project.id,
                role="assistant",
                content=content,
                intent="questionnaire_summary",
                model="system",
                cached=False,
            )
        )

    record_audit(
        "project_created",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
        detail={
            "client_name": client_name,
            "country": country,
            "questionnaire_answers": len(answers),
        },
    )
    db.session.commit()
    return jsonify({"data": project_detail(project)}), 201


@api_bp.get("/projects")
@login_required
def list_projects():
    query = Project.query
    if not is_internal(g.current_user):
        query = query.filter(Project.client_user_id == g.current_user.id)
    rows = query.order_by(Project.created_at.desc()).all()
    return jsonify({"data": [project_summary(row) for row in rows]})


@api_bp.get("/projects/<project_id>")
@login_required
def get_project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return error("not_found", "项目不存在", 404)
    if not can_access_project(g.current_user, project):
        return error("forbidden", "无权访问该项目", 403)
    return jsonify({"data": project_detail(project)})

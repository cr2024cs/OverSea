from datetime import datetime

from app.extensions import db
from app.models import Candidate, Project, Provider, Task, TaskTemplate

STAGE_LABELS = {
    0: "前期诊断与方案设计",
    1: "境内对外投资手续（ODI）",
    2: "泰国公司设立",
    3: "BOI 投资优惠",
    4: "土地、厂房与工厂许可",
    5: "设备跨境转移",
    6: "泰国员工招募与管理",
    7: "中国员工派驻",
    8: "投产后的持续合规",
}


def selection_data(project):
    value = project.selected_services_json or {}
    if isinstance(value, list):
        return {"codes": value, "source": "pm", "override_reason": None, "updated_at": None}
    return {
        "codes": value.get("codes", []),
        "source": value.get("source", "pm"),
        "override_reason": value.get("override_reason"),
        "updated_at": value.get("updated_at"),
    }


def dependency_warnings(codes, template_by_code):
    selected = set(codes)
    warnings = []
    for code in codes:
        template = template_by_code.get(code)
        if template is None:
            continue
        for predecessor in template.predecessor_codes_json or []:
            if predecessor not in selected:
                warnings.append(
                    {
                        "code": code,
                        "missing": predecessor,
                        "message": f"{code} 需要前置 {predecessor}，请同时选择或确认平台另行安排",
                    }
                )
    return warnings


def catalog_payload(project):
    templates = (
        TaskTemplate.query.filter_by(enabled=True)
        .order_by(TaskTemplate.stage_no.asc(), TaskTemplate.code.asc())
        .all()
    )
    template_by_code = {template.code: template for template in templates}
    selection = selection_data(project)
    selected = set(selection["codes"])

    grouped = {}
    for template in templates:
        grouped.setdefault(template.stage_no, []).append(
            {
                "code": template.code,
                "name": template.name,
                "category": template.category,
                "provider_type": template.provider_type,
                "deliverables": template.deliverables_json,
                "duration_days": template.duration_days,
                "fee_min_cents": template.fee_min_cents,
                "fee_max_cents": template.fee_max_cents,
                "predecessors": template.predecessor_codes_json,
                "selected": template.code in selected,
            }
        )

    return {
        "stages": [
            {
                "stage": stage,
                "stage_label": STAGE_LABELS.get(stage, f"阶段 {stage}"),
                "items": grouped[stage],
            }
            for stage in sorted(grouped)
        ],
        "selection": selection,
        "warnings": dependency_warnings(selection["codes"], template_by_code),
    }


def save_selection(project, codes, source="pm", override_reason=None):
    valid_codes = {
        row.code
        for row in TaskTemplate.query.filter_by(enabled=True).all()
    }
    cleaned = []
    for code in codes or []:
        code = str(code).strip()
        if code and code in valid_codes and code not in cleaned:
            cleaned.append(code)

    project.selected_services_json = {
        "codes": cleaned,
        "source": source,
        "override_reason": override_reason or None,
        "updated_at": datetime.utcnow().isoformat(),
    }
    return catalog_payload(project)


def _match_reason(provider, template):
    bits = []
    if provider.type == template.provider_type:
        bits.append(f"类型匹配（{provider.type}）")
    else:
        bits.append(f"类型相近（{provider.type}）")
    bits.append(provider.evidence_level)
    bits.append(provider.source_type)
    if provider.city:
        bits.append(provider.city)
    return "；".join(bits)


def _score(provider, template):
    score = 0.0
    if provider.type == template.provider_type:
        score += 50
    score += {"已核验": 20, "服务商自述": 15}.get(provider.evidence_level, 10)
    if provider.source_type == "内部库":
        score += 5
    return score


def generate_candidates(project, task_codes=None):
    selection = selection_data(project)
    codes = task_codes or selection["codes"]
    if not codes:
        raise ValueError("请先选择服务，再生成候选服务商。")

    tasks = Task.query.filter(
        Task.project_id == project.id, Task.code.in_(codes)
    ).all()
    tasks = sorted(tasks, key=lambda task: (task.stage_no, task.code))
    templates = {row.code: row for row in TaskTemplate.query.filter_by(enabled=True).all()}
    providers = Provider.query.all()

    for task in tasks:
        template = templates.get(task.code)
        if template is None:
            continue
        ranked = sorted(providers, key=lambda provider: _score(provider, template), reverse=True)[:5]
        for provider in ranked:
            candidate = Candidate.query.filter_by(
                task_id=task.id, provider_id=provider.id
            ).first()
            if candidate is None:
                candidate = Candidate(
                    project_id=project.id,
                    task_id=task.id,
                    provider_id=provider.id,
                )
                db.session.add(candidate)
            candidate.match_score = round(_score(provider, template), 1)
            candidate.reason = _match_reason(provider, template)
            candidate.evidence_json = {
                "qualification": provider.qualification,
                "city": provider.city,
                "evidence_level": provider.evidence_level,
            }
            candidate.source_type = provider.source_type
    db.session.flush()
    return candidates_payload(project)


def candidate_payload(candidate, provider, task):
    return {
        "id": candidate.id,
        "task_id": task.id,
        "task_code": task.code,
        "task_name": task.name,
        "provider_id": provider.id,
        "provider_name": provider.name,
        "provider_type": provider.type,
        "city": provider.city,
        "match_score": candidate.match_score,
        "reason": candidate.reason,
        "evidence": candidate.evidence_json,
        "source_type": candidate.source_type,
        "evidence_level": provider.evidence_level,
        "status": candidate.status,
        "reject_reason": candidate.reject_reason,
    }


def candidates_payload(project):
    rows = (
        Candidate.query.filter_by(project_id=project.id)
        .order_by(Candidate.task_id.asc(), Candidate.match_score.desc())
        .all()
    )
    grouped = {}
    for candidate in rows:
        provider = db.session.get(Provider, candidate.provider_id)
        task = db.session.get(Task, candidate.task_id)
        if provider is None or task is None:
            continue
        grouped.setdefault(
            task.code,
            {"task_id": task.id, "task_code": task.code, "task_name": task.name, "candidates": []},
        )["candidates"].append(candidate_payload(candidate, provider, task))
    return list(grouped.values())

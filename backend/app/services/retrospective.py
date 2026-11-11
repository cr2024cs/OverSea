import statistics
from datetime import datetime

from app.ai.provider import AIProvider
from app.extensions import db
from app.models import (
    ClientQuote,
    Finding,
    Milestone,
    PerformanceEvent,
    Project,
    QueryLetter,
    Quote,
    RFP,
    Task,
    TaskTemplate,
)
from app.services.quotes import provider_amount_for_project


def build_retrospective(project):
    milestones = (
        Milestone.query.filter_by(project_id=project.id)
        .order_by(Milestone.due_date.asc())
        .all()
    )
    findings = Finding.query.filter_by(project_id=project.id).all()
    client_quote = (
        ClientQuote.query.filter_by(project_id=project.id)
        .order_by(ClientQuote.version.desc())
        .first()
    )
    provider = AIProvider()
    outcome = provider.run("retrospective", {"project_id": project.id})
    result = outcome["result"] if isinstance(outcome.get("result"), dict) else {}

    planned = client_quote.total_cents if client_quote else 0
    actual = provider_amount_for_project(project.id)
    variance = round((actual - planned) / planned * 100, 2) if planned else None

    timeline = [
        {
            "name": row.name,
            "status": row.status,
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "rounds": row.rounds,
        }
        for row in milestones
    ]
    issues = {
        "total": len(findings),
        "major": sum(1 for row in findings if row.severity == "重大"),
        "closed": sum(1 for row in findings if row.closed_at is not None),
        "major_open": sum(
            1 for row in findings if row.severity == "重大" and row.closed_at is None
        ),
        "categories": sorted({row.category for row in findings}),
    }
    events = PerformanceEvent.query.filter_by(project_id=project.id).all()
    expert_totals = [
        row.expert_total for row in milestones if row.expert_total is not None
    ]

    return {
        "timeline": timeline,
        "budget": {
            "planned_cents": planned,
            "actual_cents": actual,
            "currency": client_quote.currency if client_quote else "CNY",
            "variance_percent": variance,
        },
        "issues": issues,
        "provider_performance": {
            "events": len(events),
            "average_expert_score": round(
                sum(expert_totals) / len(expert_totals), 2
            )
            if expert_totals
            else None,
            "narrative": result.get("provider_performance"),
        },
        "critical_path_variance": {
            "scheduled_days": (project.task_graph_snapshot_json or {}).get(
                "total_days", 0
            ),
            "narrative": result.get("critical_path_variance"),
        },
        "generated_at": datetime.utcnow().isoformat(),
        "model": outcome["model"],
    }


def quote_benchmark(country=None, task_code=None):
    rows = (
        db.session.query(Quote, RFP, Task, Project)
        .join(RFP, Quote.rfp_id == RFP.id)
        .join(Task, Quote.task_id == Task.id)
        .join(Project, RFP.project_id == Project.id)
        .all()
    )
    grouped = {}
    for quote, _rfp, task, project in rows:
        if country and project.country != country:
            continue
        if task_code and task.code != task_code:
            continue
        grouped.setdefault(
            task.code,
            {
                "task_code": task.code,
                "task_name": task.name,
                "currency": quote.currency,
                "amounts": [],
            },
        )["amounts"].append(quote.amount_cents)

    results = []
    for item in grouped.values():
        amounts = sorted(item.pop("amounts"))
        if not amounts:
            continue
        item.update(
            {
                "min_cents": amounts[0],
                "median_cents": int(round(statistics.median(amounts))),
                "max_cents": amounts[-1],
                "sample_count": len(amounts),
                "data_sufficient": len(amounts) >= 3,
            }
        )
        results.append(item)
    results.sort(key=lambda row: row["task_code"])
    return results


def closed_qa(query=None, task_code=None, limit=20):
    letters = QueryLetter.query.filter_by(status="closed").all()
    results = []
    needle = (query or "").strip().lower()
    for letter in letters:
        ids = letter.finding_ids_json or []
        findings = Finding.query.filter(Finding.id.in_(ids)).all() if ids else []
        task_codes = set()
        for finding in findings:
            if finding.milestone_id:
                milestone = db.session.get(Milestone, finding.milestone_id)
                if milestone and milestone.task_id:
                    task = db.session.get(Task, milestone.task_id)
                    if task:
                        task_codes.add(task.code)
        if task_code and task_code not in task_codes:
            continue
        text = " ".join(
            [
                letter.content or "",
                *[finding.question_zh or "" for finding in findings],
                *[finding.reply_text or "" for finding in findings],
            ]
        )
        if needle and needle not in text.lower():
            continue
        results.append(
            {
                "letter_id": letter.id,
                "project_id": letter.project_id,
                "task_codes": sorted(task_codes),
                "questions": [finding.question_zh for finding in findings],
                "replies": [finding.reply_text for finding in findings],
                "closed_at": letter.closed_at.isoformat() if letter.closed_at else None,
            }
        )
    return results[:limit]


def project_metrics(project_id):
    findings = Finding.query.filter_by(project_id=project_id).all()
    verified = [row for row in findings if row.citation_status == "verified"]
    closed = [row for row in findings if row.closed_at is not None]
    major = [row for row in findings if row.severity == "重大"]
    major_closed = [row for row in major if row.closed_at is not None]

    milestones = Milestone.query.filter_by(project_id=project_id).all()
    finalized = [
        row for row in milestones if row.status in {"passed", "conditional", "failed"}
    ]
    on_time = []
    for row in finalized:
        if not row.due_date:
            continue
        stamp = row.expert_submitted_at or row.client_confirmed_at
        if stamp is None:
            continue
        if stamp.date() <= row.due_date:
            on_time.append(row)

    return {
        "effective_query_rate": {
            "value": round(len([row for row in verified if row.closed_at]) / len(verified) * 100, 2)
            if verified
            else None,
            "numerator": len([row for row in verified if row.closed_at]),
            "denominator": len(verified),
        },
        "major_close_rate": {
            "value": round(len(major_closed) / len(major) * 100, 2) if major else None,
            "numerator": len(major_closed),
            "denominator": len(major),
        },
        "milestone_on_time_rate": {
            "value": round(len(on_time) / len(finalized) * 100, 2)
            if finalized
            else None,
            "numerator": len(on_time),
            "denominator": len(finalized),
        },
        "effective_match_rate": {"value": None, "note": "数据不足：需要评测专家盲评"},
        "acceptance_rate": {"value": None, "note": "数据不足：需要询价回复与档期数据"},
        "counts": {
            "findings": len(findings),
            "verified_findings": len(verified),
            "closed_findings": len(closed),
            "major_findings": len(major),
            "milestones": len(milestones),
            "finalized_milestones": len(finalized),
        },
    }

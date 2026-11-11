import hashlib
import json
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import current_app

from app.models import (
    Archive,
    AuditLog,
    Contract,
    Document,
    Finding,
    Milestone,
    PerformanceEvent,
    Proposal,
    QueryLetter,
    Task,
)
from app.services.retrospective import (
    build_retrospective,
    closed_qa,
    quote_benchmark,
)


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _proposal_export(row):
    return {
        "id": row.id,
        "version": row.version,
        "status": row.status,
        "content": row.content_json,
        "model": row.model,
        "pm_reviewed_at": row.pm_reviewed_at,
        "sent_at": row.sent_at,
        "client_confirmed_at": row.client_confirmed_at,
        "client_note": row.client_note,
        "created_at": row.created_at,
    }


def _contract_export(row):
    return {
        "id": row.id,
        "version": row.version,
        "type": row.type,
        "status": row.status,
        "scope": row.scope_json,
        "terms": row.terms_json,
        "total_cents": row.total_cents,
        "currency": row.currency,
        "file_hash": row.file_hash,
        "pm_reviewed_at": row.pm_reviewed_at,
        "client_confirmed_at": row.client_confirmed_at,
        "provider_confirmed_at": row.provider_confirmed_at,
    }


def _milestone_export(row):
    return {
        "id": row.id,
        "task_id": row.task_id,
        "provider_id": row.provider_id,
        "name": row.name,
        "deliverable": row.deliverable,
        "acceptance_criteria": row.acceptance_criteria,
        "due_date": row.due_date,
        "status": row.status,
        "acceptor_type": row.acceptor_type,
        "rounds": row.rounds,
        "submitted_at": row.submitted_at,
        "submission_note": row.submission_note,
        "submission_files": row.submission_files_json,
        "pm_review_status": row.pm_review_status,
        "pm_review_note": row.pm_review_note,
        "expert_scores": row.expert_scores_json,
        "expert_total": row.expert_total,
        "expert_comment": row.expert_comment,
        "expert_locked": row.expert_locked,
        "client_confirmed_at": row.client_confirmed_at,
    }


def _finding_export(row):
    return {
        "id": row.id,
        "milestone_id": row.milestone_id,
        "category": row.category,
        "severity": row.severity,
        "conclusion_level": row.conclusion_level,
        "quote_text": row.quote_text,
        "reason": row.reason,
        "question_zh": row.question_zh,
        "question_en": row.question_en,
        "is_legal": row.is_legal,
        "sources": row.sources_json,
        "citation_status": row.citation_status,
        "reviewer_status": row.reviewer_status,
        "reply_text": row.reply_text,
        "closed_at": row.closed_at,
    }


def build_archive(project, version):
    if not project.retrospective_json:
        project.retrospective_json = build_retrospective(project)

    documents = Document.query.filter_by(project_id=project.id).all()
    tasks = Task.query.filter_by(project_id=project.id).all()
    task_codes = {task.id: task.code for task in tasks}

    exports = {
        "project.json": {
            "id": project.id,
            "name": project.name,
            "client_name": project.client_name,
            "country": project.country,
            "industry": project.industry,
            "entry_mode": project.entry_mode,
            "goal_text": project.goal_text,
            "investment_cents": project.investment_cents,
            "currency": project.currency,
            "phase": project.phase,
            "status": project.status,
        },
        "requirement.json": project.requirement_json,
        "selection.json": project.selected_services_json,
        "proposals.json": [
            _proposal_export(row)
            for row in Proposal.query.filter_by(project_id=project.id)
            .order_by(Proposal.version.asc())
            .all()
        ],
        "contracts.json": [
            _contract_export(row)
            for row in Contract.query.filter_by(project_id=project.id)
            .order_by(Contract.version.asc())
            .all()
        ],
        "milestones.json": [
            _milestone_export(row)
            for row in Milestone.query.filter_by(project_id=project.id)
            .order_by(Milestone.due_date.asc())
            .all()
        ],
        "findings.json": [
            _finding_export(row)
            for row in Finding.query.filter_by(project_id=project.id).all()
        ],
        "query_letters.json": [
            {
                "id": row.id,
                "provider_id": row.provider_id,
                "finding_ids": row.finding_ids_json,
                "content": row.content,
                "approval_status": row.approval_status,
                "approved_by_role": row.approved_by_role,
                "status": row.status,
                "sent_at": row.sent_at,
                "closed_at": row.closed_at,
            }
            for row in QueryLetter.query.filter_by(project_id=project.id).all()
        ],
        "performance_events.json": [
            {
                "id": row.id,
                "provider_id": row.provider_id,
                "milestone_id": row.milestone_id,
                "type": row.type,
                "dimension": row.dimension,
                "value": row.value,
                "note": row.note,
                "occurred_at": row.occurred_at,
            }
            for row in PerformanceEvent.query.filter_by(project_id=project.id).all()
        ],
        "documents.json": [
            {
                "id": row.id,
                "filename": row.filename,
                "page_count": row.page_count,
                "size_bytes": row.size_bytes,
                "text": row.text_content,
            }
            for row in documents
        ],
        "audit_logs.json": [
            {
                "id": row.id,
                "action": row.action,
                "actor_label": row.actor_label,
                "object_type": row.object_type,
                "object_id": row.object_id,
                "detail": row.detail_json,
                "ip": row.ip,
                "created_at": row.created_at,
            }
            for row in AuditLog.query.filter_by(project_id=project.id)
            .order_by(AuditLog.created_at.asc())
            .all()
        ],
        "retrospective.json": project.retrospective_json,
        "benchmark.json": quote_benchmark(country=project.country),
        "qa.json": closed_qa(),
        "task_codes.json": task_codes,
    }

    archive_dir = Path(current_app.config["ARCHIVE_DIR"])
    archive_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{project.id}_v{version}_{int(time.time())}.zip"
    zip_path = archive_dir / filename
    retention_until = date.today() + timedelta(days=365)
    files = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, payload in exports.items():
            content = json.dumps(
                _jsonable(payload), ensure_ascii=False, indent=2
            ).encode("utf-8")
            bundle.writestr(name, content)
            files.append(
                {
                    "name": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "bytes": len(content),
                }
            )

        for document in documents:
            if not document.path:
                continue
            source = Path(document.path)
            if not source.exists():
                continue
            arcname = f"files/{document.id}_{Path(document.filename).name}"
            bundle.write(source, arcname)
            files.append(
                {
                    "name": arcname,
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "bytes": source.stat().st_size,
                }
            )

        manifest = {
            "project_id": project.id,
            "project_name": project.name,
            "version": version,
            "generated_at": datetime.utcnow().isoformat(),
            "retention_until": retention_until.isoformat(),
            "files": files,
            "sections": [name for name in exports],
        }
        manifest_bytes = json.dumps(
            manifest, ensure_ascii=False, indent=2
        ).encode("utf-8")
        bundle.writestr("manifest.json", manifest_bytes)

    file_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return zip_path, file_hash, manifest, retention_until


def create_archive_row(project, version, zip_path, file_hash, manifest, retention_until, user_id):
    return Archive(
        project_id=project.id,
        version=version,
        manifest_json=manifest,
        zip_path=str(zip_path),
        file_hash=file_hash,
        retention_until=retention_until,
        generated_by=user_id,
    )

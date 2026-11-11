import json
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import g, jsonify, request, send_file

from app.api import api_bp
from app.api.deps import roles_required
from app.api.errors import error
from app.extensions import db
from app.models import Archive, Finding, Milestone, Project
from app.services.archive import build_archive, create_archive_row
from app.services.audit import record_audit
from app.services.retrospective import (
    build_retrospective,
    closed_qa,
    project_metrics,
    quote_benchmark,
)
from app.services.state_machine import fire_project


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    return project, None


def _archive_payload(row, include_manifest=False):
    payload = {
        "id": row.id,
        "version": row.version,
        "file_hash": row.file_hash,
        "retention_until": row.retention_until.isoformat()
        if row.retention_until
        else None,
        "created_at": row.created_at.isoformat(),
        "download_url": f"/api/archives/{row.id}/download",
    }
    if include_manifest:
        payload["manifest"] = row.manifest_json
    return payload


@api_bp.post("/projects/<project_id>/retrospective")
@roles_required("pm", "admin")
def generate_retrospective(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    project.retrospective_json = build_retrospective(project)
    record_audit(
        "retrospective_generated",
        object_type="project",
        object_id=project.id,
        project_id=project.id,
    )
    db.session.commit()
    return jsonify({"data": project.retrospective_json})


@api_bp.get("/projects/<project_id>/retrospective")
@roles_required("pm", "admin", "lawyer")
def get_retrospective(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    if not project.retrospective_json:
        return error("not_found", "复盘报告尚未生成", 404)
    return jsonify({"data": project.retrospective_json})


@api_bp.get("/benchmarks")
@roles_required("pm", "admin", "lawyer")
def benchmarks():
    country = request.args.get("country") or None
    task_code = request.args.get("task_code") or None
    return jsonify({"data": quote_benchmark(country=country, task_code=task_code)})


@api_bp.get("/knowledge/qa")
@roles_required("pm", "admin", "lawyer")
def knowledge_qa():
    return jsonify(
        {
            "data": closed_qa(
                query=request.args.get("q"),
                task_code=request.args.get("task_code"),
                limit=int(request.args.get("limit", "20")),
            )
        }
    )


@api_bp.get("/projects/<project_id>/metrics")
@roles_required("pm", "admin", "lawyer")
def project_metrics_view(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    return jsonify({"data": project_metrics(project.id)})


@api_bp.get("/metrics/export")
@roles_required("admin")
def metrics_export():
    project_id = request.args.get("project_id")
    if project_id:
        project, failure = _project(project_id)
        if failure:
            return failure
        payload = {
            "project_id": project.id,
            "project_name": project.name,
            "metrics": project_metrics(project.id),
        }
    else:
        payload = {
            "projects": [
                {
                    "project_id": row.id,
                    "project_name": row.name,
                    "metrics": project_metrics(row.id),
                }
                for row in Project.query.all()
            ]
        }
    payload["exported_at"] = datetime.utcnow().isoformat()
    return jsonify({"data": payload})


@api_bp.post("/projects/<project_id>/archives")
@roles_required("pm", "admin")
def create_archive(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    if project.archived:
        return error("project_archived", "项目已归档，不能重复归档", 409)

    milestones = Milestone.query.filter_by(project_id=project.id).all()
    if not milestones:
        return error("validation_error", "项目没有节点，不能归档", 400)
    if any(row.status not in {"passed", "conditional"} for row in milestones):
        return error("validation_error", "存在未通过节点，不能归档", 400)
    if any(row.client_confirmed_at is None for row in milestones):
        return error("validation_error", "存在未客户确认的节点，不能归档", 400)

    open_major = Finding.query.filter_by(
        project_id=project.id, severity="重大", closed_at=None
    ).count()
    if open_major:
        return error("validation_error", "存在未关闭的重大发现，不能归档", 400)

    if not project.retrospective_json:
        project.retrospective_json = build_retrospective(project)

    version = (
        db.session.query(db.func.max(Archive.version))
        .filter(Archive.project_id == project.id)
        .scalar()
        or 0
    ) + 1
    zip_path, file_hash, manifest, retention_until = build_archive(project, version)
    row = create_archive_row(
        project,
        version,
        zip_path,
        file_hash,
        manifest,
        retention_until,
        g.current_user.id,
    )
    db.session.add(row)
    fire_project(project, "project_archived")
    project.archived_at = datetime.utcnow()
    record_audit(
        "project_archived",
        object_type="archive",
        object_id=row.id,
        project_id=project.id,
        detail={"version": version, "file_hash": file_hash},
    )
    db.session.commit()
    return jsonify({"data": _archive_payload(row, include_manifest=True)}), 201


@api_bp.get("/projects/<project_id>/archives")
@roles_required("pm", "admin")
def list_archives(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure
    rows = (
        Archive.query.filter_by(project_id=project.id)
        .order_by(Archive.version.desc())
        .all()
    )
    return jsonify({"data": [_archive_payload(row) for row in rows]})


@api_bp.get("/archives/<archive_id>")
@roles_required("pm", "admin")
def get_archive(archive_id):
    row = db.session.get(Archive, archive_id)
    if row is None:
        return error("not_found", "归档不存在", 404)
    return jsonify({"data": _archive_payload(row, include_manifest=True)})


@api_bp.get("/archives/<archive_id>/download")
@roles_required("pm", "admin")
def download_archive(archive_id):
    row = db.session.get(Archive, archive_id)
    if row is None:
        return error("not_found", "归档不存在", 404)
    path = Path(row.zip_path)
    if not path.exists():
        return error("not_found", "归档文件不存在", 404)
    return send_file(
        path,
        as_attachment=True,
        download_name=f"project-{row.project_id}-v{row.version}.zip",
        mimetype="application/zip",
    )


@api_bp.post("/admin/demo/reset")
@roles_required("admin")
def reset_demo():
    from app.seeds.seed import seed_all

    counts = seed_all(reset_demo=True)
    return jsonify({"data": counts})

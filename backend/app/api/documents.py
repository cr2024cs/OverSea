import uuid
from pathlib import Path

from flask import current_app, g, jsonify, request

from app.api import api_bp
from app.api.deps import login_required, roles_required
from app.api.errors import error
from app.extensions import db
from app.models import Document, Project
from app.services.audit import record_audit
from app.services.documents import parse_document
from app.services.permissions import can_access_project

ALLOWED_SUFFIXES = {".txt", ".md", ".docx", ".pdf"}


def _project(project_id):
    project = db.session.get(Project, project_id)
    if project is None:
        return None, error("not_found", "项目不存在", 404)
    if not can_access_project(g.current_user, project):
        return None, error("forbidden", "无权访问该项目", 403)
    return project, None


@api_bp.post("/projects/<project_id>/documents")
@roles_required("client", "pm", "admin")
def upload_document(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return error("validation_error", "请选择要上传的文件", 400)

    filename = upload.filename.replace("\\", "/").split("/")[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        return error("validation_error", "仅支持 txt、md、docx、文本型 pdf", 400)

    data = upload.read()
    max_bytes = current_app.config["MAX_UPLOAD_BYTES"]
    if len(data) > max_bytes:
        return error("payload_too_large", "文件超过大小限制", 413)

    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid.uuid4().hex}{suffix}"
    storage_path = upload_dir / storage_name
    storage_path.write_bytes(data)

    try:
        pages, text = parse_document(storage_path, filename)
    except ValueError as exc:
        storage_path.unlink(missing_ok=True)
        return error("parse_failed", str(exc), 400)
    except Exception:
        storage_path.unlink(missing_ok=True)
        return error("parse_failed", "文件解析失败，请检查格式或人工录入", 400)

    document = Document(
        project_id=project.id,
        filename=filename,
        mime=upload.mimetype,
        path=str(storage_path),
        text_content=text,
        page_texts_json=pages,
        page_count=len(pages),
        size_bytes=len(data),
    )
    db.session.add(document)
    record_audit(
        "document_uploaded",
        object_type="document",
        object_id=document.id,
        project_id=project.id,
        detail={"filename": filename, "size_bytes": len(data)},
    )
    db.session.commit()

    return (
        jsonify(
            {
                "data": {
                    "id": document.id,
                    "filename": document.filename,
                    "page_count": document.page_count,
                    "size_bytes": document.size_bytes,
                }
            }
        ),
        201,
    )


@api_bp.get("/projects/<project_id>/documents")
@login_required
def list_documents(project_id):
    project, failure = _project(project_id)
    if failure:
        return failure

    rows = (
        Document.query.filter_by(project_id=project.id)
        .order_by(Document.created_at.asc())
        .all()
    )
    return jsonify(
        {
            "data": [
                {
                    "id": row.id,
                    "filename": row.filename,
                    "page_count": row.page_count,
                    "size_bytes": row.size_bytes,
                    "uploaded_at": row.created_at.isoformat(),
                }
                for row in rows
            ]
        }
    )

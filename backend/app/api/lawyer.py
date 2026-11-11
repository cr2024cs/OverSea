from flask import jsonify

from app.api import api_bp
from app.api.deps import roles_required
from app.extensions import db
from app.models import Project, QueryLetter


@api_bp.get("/lawyer/workbench")
@roles_required("lawyer")
def lawyer_workbench():
    letters = (
        QueryLetter.query.filter_by(approval_status="pending")
        .order_by(QueryLetter.created_at.desc())
        .all()
    )
    projects = Project.query.order_by(Project.updated_at.desc()).all()
    return jsonify(
        {
            "data": {
                "pending_letters": [
                    {
                        "id": row.id,
                        "project_id": row.project_id,
                        "project_name": (
                            db.session.get(Project, row.project_id).name
                            if db.session.get(Project, row.project_id)
                            else None
                        ),
                        "status": row.status,
                        "content": row.content,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in letters
                ],
                "projects": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "client_name": row.client_name,
                        "phase": row.phase,
                        "status": row.status,
                    }
                    for row in projects
                ],
            }
        }
    )

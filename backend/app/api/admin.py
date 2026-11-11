from flask import jsonify

from app.api import api_bp
from app.api.deps import roles_required
from app.extensions import db
from app.models import (
    Archive,
    AuditLog,
    Contract,
    Milestone,
    Project,
    Provider,
    Task,
    TaskTemplate,
    User,
)


@api_bp.get("/admin/overview")
@roles_required("admin")
def admin_overview():
    audits = (
        AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()
    )
    return jsonify(
        {
            "data": {
                "counts": {
                    "users": User.query.count(),
                    "projects": Project.query.count(),
                    "providers": Provider.query.count(),
                    "task_templates": TaskTemplate.query.count(),
                    "tasks": Task.query.count(),
                    "contracts": Contract.query.count(),
                    "milestones": Milestone.query.count(),
                    "archives": Archive.query.count(),
                },
                "users": [
                    {
                        "email": row.email,
                        "name": row.name,
                        "company": row.company,
                        "role": row.role,
                        "active": row.active,
                    }
                    for row in User.query.order_by(User.role.asc()).all()
                ],
                "audit_logs": [
                    {
                        "id": row.id,
                        "action": row.action,
                        "actor": row.actor_label,
                        "object_type": row.object_type,
                        "object_id": row.object_id,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in audits
                ],
            }
        }
    )

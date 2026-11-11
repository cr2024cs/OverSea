from datetime import datetime

from app.extensions import db
from app.models.base import new_id


class PerformanceEvent(db.Model):
    __tablename__ = "performance_events"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    provider_id = db.Column(
        db.String(32), db.ForeignKey("providers.id"), nullable=False, index=True
    )
    milestone_id = db.Column(db.String(32), nullable=True)
    type = db.Column(db.String(60), nullable=False)
    dimension = db.Column(db.String(40), nullable=False, default="delivery")
    value = db.Column(db.Float, nullable=True)
    note = db.Column(db.Text, nullable=True)
    occurred_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

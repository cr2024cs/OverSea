from datetime import datetime

from app.extensions import db
from app.models.base import TimestampMixin, new_id


class Candidate(TimestampMixin, db.Model):
    __tablename__ = "candidates"
    __table_args__ = (
        db.UniqueConstraint("task_id", "provider_id", name="uq_candidate_task_provider"),
    )

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    task_id = db.Column(db.String(32), db.ForeignKey("tasks.id"), nullable=False, index=True)
    provider_id = db.Column(
        db.String(32), db.ForeignKey("providers.id"), nullable=False, index=True
    )
    match_score = db.Column(db.Float, nullable=False, default=0)
    reason = db.Column(db.Text, nullable=True)
    evidence_json = db.Column(db.JSON, nullable=False, default=dict)
    source_type = db.Column(db.String(40), nullable=False, default="内部库")
    status = db.Column(db.String(20), nullable=False, default="shortlisted")
    reject_reason = db.Column(db.String(255), nullable=True)


class ClientQuote(db.Model):
    __tablename__ = "client_quotes"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    provider_amount_cents = db.Column(db.BigInteger, nullable=False, default=0)
    lawyer_amount_cents = db.Column(db.BigInteger, nullable=False, default=0)
    management_fee_rate = db.Column(db.Float, nullable=False, default=0.175)
    management_fee_cents = db.Column(db.BigInteger, nullable=False, default=0)
    total_cents = db.Column(db.BigInteger, nullable=False, default=0)
    currency = db.Column(db.String(10), nullable=False, default="CNY")
    status = db.Column(db.String(20), nullable=False, default="draft")
    sent_at = db.Column(db.DateTime, nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    confirm_ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

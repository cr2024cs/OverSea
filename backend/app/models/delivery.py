from app.extensions import db
from app.models.base import TimestampMixin, new_id


class Milestone(TimestampMixin, db.Model):
    __tablename__ = "milestones"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    task_id = db.Column(db.String(32), db.ForeignKey("tasks.id"), nullable=True)
    contract_id = db.Column(db.String(32), db.ForeignKey("contracts.id"), nullable=True)
    provider_id = db.Column(db.String(32), db.ForeignKey("providers.id"), nullable=True)
    expert_user_id = db.Column(db.String(32), db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    deliverable = db.Column(db.Text, nullable=True)
    acceptance_criteria = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="pending_submission")
    acceptor_type = db.Column(db.String(20), nullable=False, default="pm")
    grace_days = db.Column(db.Integer, nullable=False, default=3)
    expert_name = db.Column(db.String(120), nullable=True)
    expert_scores_json = db.Column(db.JSON, nullable=False, default=dict)
    expert_comment = db.Column(db.Text, nullable=True)
    expert_total = db.Column(db.Float, nullable=True)
    rounds = db.Column(db.Integer, nullable=False, default=0)
    submitted_at = db.Column(db.DateTime, nullable=True)
    submission_files_json = db.Column(db.JSON, nullable=False, default=list)
    submission_note = db.Column(db.Text, nullable=True)
    pm_review_status = db.Column(db.String(20), nullable=True)
    pm_review_note = db.Column(db.Text, nullable=True)
    expert_submitted_at = db.Column(db.DateTime, nullable=True)
    expert_locked = db.Column(db.Boolean, nullable=False, default=False)
    client_confirmed_at = db.Column(db.DateTime, nullable=True)
    client_confirm_ip = db.Column(db.String(64), nullable=True)


class Finding(TimestampMixin, db.Model):
    __tablename__ = "findings"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    milestone_id = db.Column(db.String(32), db.ForeignKey("milestones.id"), nullable=True)
    category = db.Column(db.String(60), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="一般")
    conclusion_level = db.Column(db.String(40), nullable=False, default="needs_verification")
    quote_text = db.Column(db.Text, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    question_zh = db.Column(db.Text, nullable=True)
    question_en = db.Column(db.Text, nullable=True)
    is_legal = db.Column(db.Boolean, nullable=False, default=False)
    sources_json = db.Column(db.JSON, nullable=False, default=list)
    citation_status = db.Column(db.String(20), nullable=False, default="verified")
    reviewer_status = db.Column(db.String(20), nullable=False, default="pending")
    reviewer_id = db.Column(db.String(32), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reject_reason = db.Column(db.String(255), nullable=True)
    reply_text = db.Column(db.Text, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)


class QueryLetter(TimestampMixin, db.Model):
    __tablename__ = "query_letters"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    provider_id = db.Column(db.String(32), db.ForeignKey("providers.id"), nullable=True)
    finding_ids_json = db.Column(db.JSON, nullable=False, default=list)
    content = db.Column(db.Text, nullable=True)
    approval_status = db.Column(db.String(20), nullable=False, default="pending")
    approved_by = db.Column(db.String(32), nullable=True)
    approved_by_role = db.Column(db.String(20), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="draft")
    sent_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

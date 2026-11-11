from app.extensions import db
from app.models.base import TimestampMixin, new_id


class Project(TimestampMixin, db.Model):
    __tablename__ = "projects"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    name = db.Column(db.String(200), nullable=False)
    client_name = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(120), nullable=True)
    contact_email = db.Column(db.String(200), nullable=True)
    contact_phone = db.Column(db.String(60), nullable=True)
    country = db.Column(db.String(20), nullable=False)
    industry = db.Column(db.String(40), nullable=False)
    entry_mode = db.Column(db.String(40), nullable=False)
    goal_text = db.Column(db.Text, nullable=True)
    investment_cents = db.Column(db.BigInteger, nullable=True)
    currency = db.Column(db.String(10), nullable=False, default="USD")
    phase = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(40), nullable=False, default="draft", index=True)
    selected_services_json = db.Column(db.JSON, nullable=False, default=list)
    total_quote_json = db.Column(db.JSON, nullable=False, default=dict)
    requirement_confirmed_at = db.Column(db.DateTime, nullable=True)
    requirement_json = db.Column(db.JSON, nullable=False, default=dict)
    task_graph_snapshot_json = db.Column(db.JSON, nullable=False, default=dict)
    retrospective_json = db.Column(db.JSON, nullable=False, default=dict)
    questionnaire_json = db.Column(db.JSON, nullable=False, default=dict)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.String(32), nullable=True)
    client_user_id = db.Column(
        db.String(32), db.ForeignKey("users.id"), nullable=True, index=True
    )


class Document(TimestampMixin, db.Model):
    __tablename__ = "documents"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(120), nullable=True)
    path = db.Column(db.String(500), nullable=True)
    text_content = db.Column(db.Text, nullable=True)
    page_texts_json = db.Column(db.JSON, nullable=False, default=list)
    page_count = db.Column(db.Integer, nullable=True)
    size_bytes = db.Column(db.BigInteger, nullable=True)


class Fact(TimestampMixin, db.Model):
    __tablename__ = "facts"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    key = db.Column(db.String(200), nullable=False)
    value = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="unknown")
    doc_id = db.Column(db.String(32), db.ForeignKey("documents.id"), nullable=True)
    page = db.Column(db.Integer, nullable=True)
    char_start = db.Column(db.Integer, nullable=True)
    char_end = db.Column(db.Integer, nullable=True)
    quote = db.Column(db.Text, nullable=True)
    citation_status = db.Column(db.String(20), nullable=False, default="unverified")
    version = db.Column(db.Integer, nullable=False, default=1)


class TaskTemplate(TimestampMixin, db.Model):
    __tablename__ = "task_templates"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(20), nullable=False, default="TH")
    industry = db.Column(db.String(40), nullable=False, default="manufacturing")
    entry_mode = db.Column(db.String(40), nullable=False, default="greenfield")
    category = db.Column(db.String(60), nullable=True)
    provider_type = db.Column(db.String(60), nullable=True)
    stage_no = db.Column(db.Integer, nullable=False, default=0)
    trigger_condition = db.Column(db.Text, nullable=True)
    required_info_json = db.Column(db.JSON, nullable=False, default=list)
    deliverables_json = db.Column(db.JSON, nullable=False, default=list)
    duration_days = db.Column(db.Integer, nullable=False, default=30)
    fee_min_cents = db.Column(db.BigInteger, nullable=False, default=0)
    fee_max_cents = db.Column(db.BigInteger, nullable=False, default=0)
    predecessor_codes_json = db.Column(db.JSON, nullable=False, default=list)
    qualification = db.Column(db.String(255), nullable=True)
    review_checklist_json = db.Column(db.JSON, nullable=False, default=list)
    legal_basis = db.Column(db.Text, nullable=True)
    effective_date = db.Column(db.Date, nullable=True)
    last_reviewed = db.Column(db.Date, nullable=True)
    reviewer = db.Column(db.String(120), nullable=True)
    is_critical = db.Column(db.Boolean, nullable=False, default=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)


class Task(TimestampMixin, db.Model):
    __tablename__ = "tasks"
    __table_args__ = (db.UniqueConstraint("project_id", "code", name="uq_task_project_code"),)

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    template_id = db.Column(db.String(32), db.ForeignKey("task_templates.id"), nullable=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    stage_no = db.Column(db.Integer, nullable=False, default=0)
    category = db.Column(db.String(60), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="pending")
    is_critical = db.Column(db.Boolean, nullable=False, default=False)
    locked = db.Column(db.Boolean, nullable=False, default=False)
    due_date = db.Column(db.Date, nullable=True)
    duration_days = db.Column(db.Integer, nullable=False, default=30)
    acceptance_criteria = db.Column(db.Text, nullable=True)
    deliverables_json = db.Column(db.JSON, nullable=False, default=list)
    predecessor_codes_json = db.Column(db.JSON, nullable=False, default=list)
    is_external = db.Column(db.Boolean, nullable=False, default=False)


class Proposal(TimestampMixin, db.Model):
    __tablename__ = "proposals"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(30), nullable=False, default="draft")
    content_json = db.Column(db.JSON, nullable=False, default=dict)
    model = db.Column(db.String(80), nullable=True)
    pm_reviewed_by = db.Column(db.String(32), nullable=True)
    pm_reviewed_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    client_confirmed_at = db.Column(db.DateTime, nullable=True)
    client_confirm_ip = db.Column(db.String(64), nullable=True)
    client_note = db.Column(db.Text, nullable=True)

from app.extensions import db
from app.models.base import TimestampMixin, new_id


class Provider(TimestampMixin, db.Model):
    __tablename__ = "providers"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    name = db.Column(db.String(200), unique=True, nullable=False)
    type = db.Column(db.String(60), nullable=False, index=True)
    country = db.Column(db.String(20), nullable=False, default="Thailand")
    city = db.Column(db.String(80), nullable=True)
    description = db.Column(db.Text, nullable=True)
    qualification = db.Column(db.String(255), nullable=True)
    evidence_level = db.Column(db.String(40), nullable=False, default="公开信息")
    source_type = db.Column(db.String(40), nullable=False, default="内部库")
    contact_name = db.Column(db.String(120), nullable=True)
    contact_email = db.Column(db.String(200), nullable=True)


class RFP(TimestampMixin, db.Model):
    __tablename__ = "rfps"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    task_id = db.Column(db.String(32), db.ForeignKey("tasks.id"), nullable=False, index=True)
    provider_id = db.Column(db.String(32), db.ForeignKey("providers.id"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    content_zh = db.Column(db.Text, nullable=True)
    content_en = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="draft")
    token = db.Column(db.String(200), unique=True, nullable=True, index=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    opened_at = db.Column(db.DateTime, nullable=True)


class Quote(TimestampMixin, db.Model):
    __tablename__ = "quotes"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    rfp_id = db.Column(db.String(32), db.ForeignKey("rfps.id"), nullable=False, index=True)
    provider_id = db.Column(db.String(32), db.ForeignKey("providers.id"), nullable=False)
    task_id = db.Column(db.String(32), db.ForeignKey("tasks.id"), nullable=False)
    currency = db.Column(db.String(10), nullable=False, default="CNY")
    amount_cents = db.Column(db.BigInteger, nullable=False, default=0)
    items_json = db.Column(db.JSON, nullable=False, default=list)
    assumptions = db.Column(db.Text, nullable=True)
    exclusions = db.Column(db.Text, nullable=True)
    payment_terms = db.Column(db.Text, nullable=True)
    raw_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="received")


class Contract(TimestampMixin, db.Model):
    __tablename__ = "contracts"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    type = db.Column(db.String(30), nullable=False, default="master")
    scope_json = db.Column(db.JSON, nullable=False, default=dict)
    total_cents = db.Column(db.BigInteger, nullable=False, default=0)
    currency = db.Column(db.String(10), nullable=False, default="CNY")
    terms_json = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(30), nullable=False, default="draft")
    file_hash = db.Column(db.String(128), nullable=True)
    pm_reviewed_by = db.Column(db.String(32), nullable=True)
    pm_reviewed_at = db.Column(db.DateTime, nullable=True)
    client_confirmed_at = db.Column(db.DateTime, nullable=True)
    client_confirm_ip = db.Column(db.String(64), nullable=True)
    provider_confirmed_at = db.Column(db.DateTime, nullable=True)
    provider_confirm_ip = db.Column(db.String(64), nullable=True)

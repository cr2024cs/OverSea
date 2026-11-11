from app.extensions import db
from app.models.base import TimestampMixin, new_id


class KnowledgeChunk(TimestampMixin, db.Model):
    __tablename__ = "knowledge_chunks"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    doc_code = db.Column(db.String(10), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(40), nullable=False, default="Thailand")
    industry = db.Column(db.String(40), nullable=False, default="Manufacturing")
    topic = db.Column(db.String(120), nullable=True)
    source_priority = db.Column(db.String(40), nullable=True)
    last_reviewed = db.Column(db.Date, nullable=True)
    seq = db.Column(db.Integer, nullable=False, default=0)
    heading_path = db.Column(db.String(500), nullable=True)
    content = db.Column(db.Text, nullable=False)
    char_start = db.Column(db.Integer, nullable=False, default=0)
    char_end = db.Column(db.Integer, nullable=False, default=0)

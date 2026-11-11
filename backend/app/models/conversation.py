from datetime import datetime

from app.extensions import db
from app.models.base import TimestampMixin, new_id


class Conversation(TimestampMixin, db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, default="新对话")
    created_by = db.Column(db.String(32), nullable=True)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.String(32), primary_key=True, default=new_id)
    conversation_id = db.Column(
        db.String(32), db.ForeignKey("conversations.id"), nullable=False, index=True
    )
    project_id = db.Column(db.String(32), db.ForeignKey("projects.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="user")
    content = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(40), nullable=True)
    citations_json = db.Column(db.JSON, nullable=False, default=list)
    model = db.Column(db.String(80), nullable=True)
    cached = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

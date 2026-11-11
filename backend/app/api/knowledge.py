from datetime import date

from flask import jsonify, request

from app.api import api_bp
from app.api.deps import login_required
from app.api.errors import error
from app.extensions import db
from app.models import KnowledgeChunk
from app.services.rag import search_knowledge


@api_bp.get("/knowledge/search")
@login_required
def knowledge_search():
    query = request.args.get("q", "").strip()
    if not query:
        return error("validation_error", "缺少检索问题 q", 400)

    limit = request.args.get("limit", "8")
    try:
        limit = int(limit)
    except ValueError:
        limit = 8

    results = search_knowledge(
        query,
        country=request.args.get("country") or None,
        industry=request.args.get("industry") or None,
        limit=limit,
    )
    return jsonify({"data": results})


@api_bp.get("/knowledge/chunks/<chunk_id>")
@login_required
def knowledge_chunk(chunk_id):
    chunk = db.session.get(KnowledgeChunk, chunk_id)
    if chunk is None:
        return error("not_found", "知识块不存在", 404)

    stale = bool(
        chunk.last_reviewed
        and (date.today() - chunk.last_reviewed).days > 180
    )
    return jsonify(
        {
            "data": {
                "id": chunk.id,
                "doc_code": chunk.doc_code,
                "title": chunk.title,
                "heading_path": chunk.heading_path,
                "content": chunk.content,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "last_reviewed": chunk.last_reviewed.isoformat()
                if chunk.last_reviewed
                else None,
                "stale": stale,
            }
        }
    )

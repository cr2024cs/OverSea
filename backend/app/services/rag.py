import math
import re
from datetime import date

from app.extensions import db
from app.models import KnowledgeChunk

TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]+")

SYNONYM_GROUPS = [
    {"boi", "投资优惠", "投资促进", "投资促进委员会"},
    {"eia", "iee", "ehia", "环评", "环境评估", "环境影响"},
    {"work permit", "工作许可", "工作证", "外籍员工"},
    {"odi", "境外投资", "对外投资", "备案", "核准"},
    {"land", "土地", "购地", "租赁", "厂房"},
    {"tax", "税务", "所得税", "增值税"},
    {"customs", "海关", "清关", "进口"},
    {"labor", "劳动", "用工", "员工", "社保"},
]

COUNTRY_ALIASES = {"TH": "Thailand", "thailand": "Thailand"}
INDUSTRY_ALIASES = {
    "manufacturing": "Manufacturing",
    "manufacture": "Manufacturing",
    "制造业": "Manufacturing",
}


def tokenize(query):
    terms = set()
    for token in TOKEN_RE.findall((query or "").lower()):
        if token.isascii():
            terms.add(token)
        else:
            terms.add(token)
            if len(token) >= 2:
                for index in range(len(token) - 1):
                    terms.add(token[index : index + 2])
    return terms


def expand_terms(terms):
    expanded = set(terms)
    for group in SYNONYM_GROUPS:
        if any(term in group for term in terms):
            expanded.update(group)
    return expanded


def _score(chunk, terms):
    heading = (chunk.heading_path or "").lower()
    content = (chunk.content or "").lower()
    haystack = f"{heading} {content}"
    score = 0.0
    for term in terms:
        if not term:
            continue
        score += haystack.count(term)
        if term in heading:
            score += 2.0
    if chunk.source_priority == "Official":
        score *= 1.1
    return score / math.sqrt(max(len(content), 200))


def search_knowledge(query, country=None, industry=None, limit=8):
    terms = expand_terms(tokenize(query))
    if not terms:
        return []

    statement = KnowledgeChunk.query
    if country:
        normalized = COUNTRY_ALIASES.get(
            country, COUNTRY_ALIASES.get(country.lower(), country)
        )
        statement = statement.filter(
            db.func.lower(KnowledgeChunk.country) == normalized.lower()
        )
    if industry:
        normalized = INDUSTRY_ALIASES.get(
            industry, INDUSTRY_ALIASES.get(industry.lower(), industry)
        )
        statement = statement.filter(
            db.func.lower(KnowledgeChunk.industry) == normalized.lower()
        )

    rows = statement.all()
    today = date.today()
    scored = []
    for chunk in rows:
        score = _score(chunk, terms)
        if score <= 0:
            continue
        stale = bool(
            chunk.last_reviewed and (today - chunk.last_reviewed).days > 180
        )
        scored.append(
            {
                "chunk_id": chunk.id,
                "doc_code": chunk.doc_code,
                "title": chunk.title,
                "heading_path": chunk.heading_path,
                "content": chunk.content,
                "snippet": (chunk.content or "")[:240],
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "last_reviewed": chunk.last_reviewed.isoformat()
                if chunk.last_reviewed
                else None,
                "stale": stale,
                "score": round(score, 4),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, min(int(limit), 20))]

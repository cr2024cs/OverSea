from app.services.citation import verify_quote

CATEGORIES = [
    "覆盖度",
    "依据",
    "条件",
    "事实一致性",
    "失败路径与替代方案",
    "跨专业冲突",
    "内部一致性",
]

SEVERITIES = ["重大", "一般", "提示"]
CONCLUSIONS = ["verified_error", "needs_verification", "professional_judgment"]


def _clickable_sources(sources):
    return [
        source
        for source in (sources or [])
        if isinstance(source, dict) and source.get("clickable")
    ]


def classify_conclusion(level, sources, citation_verified):
    if level not in CONCLUSIONS:
        level = "needs_verification"
    if level == "verified_error":
        if not _clickable_sources(sources) or not citation_verified:
            return "needs_verification"
    return level


def normalize_findings(raw_findings, source_text=""):
    results = []
    for item in raw_findings or []:
        quote = (item.get("quote_text") or "").strip()
        sources = item.get("sources") or item.get("sources_json") or []
        clickable = _clickable_sources(sources)
        citation_verified = bool(
            quote and source_text and verify_quote(quote, source_text)
        )
        if not citation_verified and clickable:
            citation_verified = True
        level = classify_conclusion(
            item.get("conclusion_level", "needs_verification"),
            sources,
            citation_verified,
        )
        severity = item.get("severity") if item.get("severity") in SEVERITIES else "一般"
        category = item.get("category")
        if category not in CATEGORIES:
            category = "依据"
        results.append(
            {
                "category": category,
                "severity": severity,
                "conclusion_level": level,
                "quote_text": quote,
                "reason": item.get("reason"),
                "question_zh": item.get("question_zh"),
                "question_en": item.get("question_en"),
                "is_legal": bool(item.get("is_legal")),
                "sources_json": sources,
                "citation_status": "verified" if citation_verified else "unverified",
                "reviewer_status": "pending",
            }
        )
    return results

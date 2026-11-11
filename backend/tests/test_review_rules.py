import json
from pathlib import Path

from app.services.review import classify_conclusion, normalize_findings

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "findings.json"


def test_verified_error_without_source_is_downgraded():
    assert (
        classify_conclusion("verified_error", [], citation_verified=True)
        == "needs_verification"
    )


def test_verified_error_with_clickable_source_stays():
    sources = [{"clickable": True, "url": "https://example.com"}]
    assert (
        classify_conclusion("verified_error", sources, citation_verified=True)
        == "verified_error"
    )


def test_normalize_findings_marks_unverified_quote():
    raw = [
        {
            "category": "内部一致性",
            "severity": "重大",
            "conclusion_level": "verified_error",
            "quote_text": "不存在的引用",
            "sources": [],
        }
    ]
    result = normalize_findings(raw, "服务商答复原文")
    assert result[0]["conclusion_level"] == "needs_verification"
    assert result[0]["citation_status"] == "unverified"


def test_normalize_fixture_has_expected_levels():
    with FIXTURE.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)["findings"]
    result = normalize_findings(raw, "")
    levels = [item["conclusion_level"] for item in result]
    assert len(result) == 8
    assert levels.count("verified_error") == 3
    assert levels.count("professional_judgment") == 1
    assert levels.count("needs_verification") == 4
    assert all(item["citation_status"] == "verified" for item in result)
    assert sum(1 for item in result if item["is_legal"]) == 6

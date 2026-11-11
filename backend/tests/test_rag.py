from app.seeds.seed import seed_all
from app.services.rag import search_knowledge
from tests.helpers import bearer, login_token


def test_rag_search_boi(app):
    with app.app_context():
        seed_all()
        results = search_knowledge(
            "BOI 投资优惠", country="TH", industry="manufacturing", limit=8
        )

    assert results
    assert len(results) <= 8
    assert "01" in {item["doc_code"] for item in results}
    assert all(item["stale"] is False for item in results)
    assert results[0]["heading_path"]


def test_rag_search_synonyms(app):
    with app.app_context():
        seed_all()
        environmental = search_knowledge("环评 EIA", country="TH", limit=8)
        work_permit = search_knowledge("工作许可", country="TH", limit=8)

    assert any(item["doc_code"] == "05" for item in environmental)
    assert any(item["doc_code"] == "07" for item in work_permit)


def test_rag_country_filter(app):
    with app.app_context():
        seed_all()
        assert search_knowledge("BOI", country="VN") == []


def test_knowledge_endpoints(app):
    with app.app_context():
        seed_all()

    client = app.test_client()
    headers = bearer(login_token(client))

    search = client.get(
        "/api/knowledge/search",
        query_string={"q": "BOI 投资优惠", "country": "TH", "limit": 3},
        headers=headers,
    )
    assert search.status_code == 200
    results = search.get_json()["data"]
    assert 0 < len(results) <= 3

    chunk = client.get(
        f"/api/knowledge/chunks/{results[0]['chunk_id']}", headers=headers
    )
    assert chunk.status_code == 200
    assert chunk.get_json()["data"]["content"]

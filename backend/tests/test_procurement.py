from app.models import Project
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _setup(app):
    with app.app_context():
        seed_all()
        return Project.query.filter_by(name="泰国春武里汽车零部件工厂").first().id


def _client(app):
    client = app.test_client()
    return client, bearer(login_token(client))


def _prepare(client, headers, project_id, codes):
    client.post(
        f"/api/projects/{project_id}/selection",
        json={"codes": codes, "override_reason": "演示选择"},
        headers=headers,
    )
    response = client.post(
        f"/api/projects/{project_id}/candidates/generate",
        json={"task_codes": codes},
        headers=headers,
    )
    assert response.status_code == 200


def _client_token(client, headers, project_id):
    return client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "client", "subject_id": "client-a"},
        headers=headers,
    ).get_json()["data"]["token"]


def test_rfp_requires_approval_and_tracks_open(app):
    project_id = _setup(app)
    client, headers = _client(app)
    _prepare(client, headers, project_id, ["T11"])

    created = client.post(
        f"/api/projects/{project_id}/rfps",
        json={"task_codes": ["T11"]},
        headers=headers,
    )
    assert created.status_code == 201
    rfps = created.get_json()["data"]
    assert rfps
    assert all("长三角民营汽车零部件制造企业" not in item.get("content_zh", "") for item in rfps)

    draft = next(item for item in rfps if item["status"] == "draft")
    early_send = client.post(f"/api/rfps/{draft['id']}/send", headers=headers)
    assert early_send.status_code == 409

    approved = client.post(f"/api/rfps/{draft['id']}/approve", headers=headers)
    assert approved.get_json()["data"]["status"] == "approved"

    sent = client.post(f"/api/rfps/{draft['id']}/send", headers=headers)
    assert sent.get_json()["data"]["status"] == "sent"

    link = client.get(f"/api/rfp-link/{draft['token']}")
    assert link.status_code == 200
    data = link.get_json()["data"]
    assert data["task_code"] == "T11"
    assert "已隐去" in data["content_zh"]
    assert "长三角民营汽车零部件制造企业" not in data["content_zh"]

    listed = client.get(f"/api/projects/{project_id}/rfps", headers=headers).get_json()["data"]
    opened = next(item for item in listed if item["id"] == draft["id"])
    assert opened["opened_at"] is not None


def test_quote_submission_parsing_and_comparison(app):
    project_id = _setup(app)
    client, headers = _client(app)
    _prepare(client, headers, project_id, ["T11"])

    rfps = client.post(
        f"/api/projects/{project_id}/rfps",
        json={"task_codes": ["T11"]},
        headers=headers,
    ).get_json()["data"]
    draft = next(item for item in rfps if item["status"] == "draft")
    client.post(f"/api/rfps/{draft['id']}/approve", headers=headers)
    client.post(f"/api/rfps/{draft['id']}/send", headers=headers)

    submitted = client.post(
        f"/api/rfp-link/{draft['token']}/quote",
        json={"raw_text": "报价合计 52 万元人民币", "assumptions": "含差旅"},
    )
    assert submitted.status_code == 201
    quote = submitted.get_json()["data"]
    assert quote["amount_cents"] == 52_000_000
    assert quote["currency"] == "CNY"

    corrected = client.patch(
        f"/api/quotes/{quote['id']}",
        json={"amount_cents": 50_000_000},
        headers=headers,
    )
    assert corrected.status_code == 200

    comparison = client.get(
        f"/api/projects/{project_id}/quote-comparison", headers=headers
    ).get_json()["data"]
    t11 = next(row for row in comparison["tasks"] if row["task_code"] == "T11")
    assert len(t11["quotes"]) >= 2
    assert t11["lowest_amount_cents"] == 40_000_000
    assert any(row["is_lowest"] for row in t11["quotes"])
    assert t11["spread_percent"] > 0
    assert comparison["provider_amount_cents"] >= 40_000_000


def test_client_quote_versions_send_and_confirm(app):
    project_id = _setup(app)
    client, headers = _client(app)
    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        project.phase = 3
        project.status = "service_selecting"
        from app.extensions import db

        db.session.commit()
    token = _client_token(client, headers, project_id)

    first = client.post(
        f"/api/projects/{project_id}/client-quotes", json={}, headers=headers
    )
    assert first.status_code == 201
    v1 = first.get_json()["data"]
    assert v1["provider_amount_cents"] == 40_000_000
    assert v1["management_fee_cents"] == 7_000_000
    assert v1["total_cents"] == 47_000_000
    assert v1["version"] == 1

    before_send = client.get(f"/api/link/{token}/client-quote")
    assert before_send.status_code == 409

    second = client.post(
        f"/api/projects/{project_id}/client-quotes",
        json={"management_fee_rate": 20},
        headers=headers,
    ).get_json()["data"]
    assert second["version"] == 2
    assert second["management_fee_cents"] == 8_000_000
    assert second["total_cents"] == 48_000_000

    sent = client.post(f"/api/client-quotes/{second['id']}/send", headers=headers)
    assert sent.get_json()["data"]["status"] == "sent"

    link = client.get(f"/api/link/{token}/client-quote")
    assert link.status_code == 200
    assert link.get_json()["data"]["version"] == 2

    confirmed = client.post(f"/api/link/{token}/client-quote/confirm")
    assert confirmed.status_code == 200
    data = confirmed.get_json()["data"]
    assert data["status"] == "confirmed"
    confirmed_at = data["confirmed_at"]
    assert confirmed_at

    repeated = client.post(f"/api/link/{token}/client-quote/confirm")
    assert repeated.get_json()["data"]["confirmed_at"] == confirmed_at

    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        assert project.status == "quote_confirmed"


def test_client_quote_link_rejects_provider_token(app):
    project_id = _setup(app)
    client, headers = _client(app)
    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        project.phase = 3
        project.status = "service_selecting"
        from app.extensions import db

        db.session.commit()
    quote = client.post(
        f"/api/projects/{project_id}/client-quotes", json={}, headers=headers
    ).get_json()["data"]
    client.post(f"/api/client-quotes/{quote['id']}/send", headers=headers)

    provider_token = client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "provider"},
        headers=headers,
    ).get_json()["data"]["token"]
    response = client.get(f"/api/link/{provider_token}/client-quote")
    assert response.status_code == 403

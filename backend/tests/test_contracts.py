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


def _client_token(client, headers, project_id):
    return client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "client", "subject_id": "client-a"},
        headers=headers,
    ).get_json()["data"]["token"]


def _prepare_contract(app, client, headers, project_id):
    client.post(
        f"/api/projects/{project_id}/selection",
        json={"codes": ["T11"], "override_reason": "合同测试"},
        headers=headers,
    )
    client.post(
        f"/api/projects/{project_id}/candidates/generate",
        json={"task_codes": ["T11"]},
        headers=headers,
    )
    rfps = client.post(
        f"/api/projects/{project_id}/rfps",
        json={"task_codes": ["T11"]},
        headers=headers,
    ).get_json()["data"]
    draft = next(item for item in rfps if item["status"] == "draft")
    client.post(f"/api/rfps/{draft['id']}/approve", headers=headers)
    client.post(f"/api/rfps/{draft['id']}/send", headers=headers)
    client.post(
        f"/api/rfp-link/{draft['token']}/quote",
        json={"raw_text": "报价合计 50 万元人民币"},
    )

    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        project.phase = 3
        project.status = "service_selecting"
        from app.extensions import db

        db.session.commit()

    client_quote = client.post(
        f"/api/projects/{project_id}/client-quotes", json={}, headers=headers
    ).get_json()["data"]
    client.post(
        f"/api/client-quotes/{client_quote['id']}/send", headers=headers
    )
    token = _client_token(client, headers, project_id)
    client.post(f"/api/link/{token}/client-quote/confirm")
    return token


def test_contract_generation_and_dual_confirmation(app):
    project_id = _setup(app)
    client, headers = _client(app)
    client_token = _prepare_contract(app, client, headers, project_id)

    generated = client.post(
        f"/api/projects/{project_id}/contracts", headers=headers
    )
    assert generated.status_code == 201, generated.get_json()
    contract = generated.get_json()["data"]
    assert contract["type"] == "master"
    assert contract["status"] == "draft"
    assert contract["total_cents"] == 47_000_000
    assert len(contract["file_hash"]) == 64
    assert contract["milestones"]
    assert contract["milestones"][0]["task_code"] == "T11"
    assert contract["provider_contracts"]
    assert "不构成电子签名" in contract["terms"]["disclaimer"]

    early_client = client.post(f"/api/link/{client_token}/contract/confirm")
    assert early_client.status_code == 409

    reviewed = client.post(
        f"/api/contracts/{contract['id']}/review", headers=headers
    )
    assert reviewed.get_json()["data"]["status"] == "pending_client"

    client_confirm = client.post(f"/api/link/{client_token}/contract/confirm")
    assert client_confirm.status_code == 200
    assert client_confirm.get_json()["data"]["status"] == "pending_provider"

    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        assert project.phase == 5
        assert project.status != "executing"

    provider_id = contract["provider_contracts"][0]["provider_id"]
    provider_token = client.post(
        "/api/access-tokens",
        json={
            "project_id": project_id,
            "role_type": "provider",
            "subject_id": provider_id,
        },
        headers=headers,
    ).get_json()["data"]["token"]

    provider_view = client.get(f"/api/link/{provider_token}/contract")
    assert provider_view.status_code == 200
    assert provider_view.get_json()["data"]["actor"] == "provider"

    provider_confirm = client.post(f"/api/link/{provider_token}/contract/confirm")
    assert provider_confirm.status_code == 200
    assert provider_confirm.get_json()["data"]["status"] == "active"

    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        assert project.phase == 6
        assert project.status == "executing"

    repeated = client.post(f"/api/link/{provider_token}/contract/confirm")
    assert repeated.get_json()["data"]["status"] == "active"


def test_contract_requires_confirmed_client_quote(app):
    project_id = _setup(app)
    client, headers = _client(app)

    response = client.post(
        f"/api/projects/{project_id}/contracts", headers=headers
    )
    assert response.status_code == 400
    assert "总报价" in response.get_json()["message"]


def test_provider_token_must_bind_provider(app):
    project_id = _setup(app)
    client, headers = _client(app)
    client_token = _prepare_contract(app, client, headers, project_id)
    contract = client.post(
        f"/api/projects/{project_id}/contracts", headers=headers
    ).get_json()["data"]
    client.post(f"/api/contracts/{contract['id']}/review", headers=headers)
    client.post(f"/api/link/{client_token}/contract/confirm")

    unbound = client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "provider"},
        headers=headers,
    ).get_json()["data"]["token"]
    response = client.get(f"/api/link/{unbound}/contract")
    assert response.status_code == 403

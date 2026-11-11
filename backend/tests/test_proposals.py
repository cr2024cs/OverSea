import json

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


def _generate(client, headers, project_id):
    response = client.post(
        f"/api/projects/{project_id}/proposals", headers=headers
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_generate_proposal_has_eight_chapters_and_budget(app):
    project_id = _setup(app)
    client, headers = _client(app)

    proposal = _generate(client, headers, project_id)
    content = proposal["content"]

    assert proposal["version"] == 1
    assert proposal["status"] == "generated"
    assert len(content["chapters"]) == 8
    budget = content["budget"]
    assert 0 < budget["low_cents"] < budget["mid_cents"] < budget["high_cents"]
    assert "任务模板费用区间" in budget["basis"]
    assert "非正式报价" in content["disclaimer"]
    assert content["references"]
    assert content["services"]

    serialized = json.dumps(content, ensure_ascii=False)
    assert "曼谷商法律师事务所" not in serialized
    assert "泰中投资法律服务中心" not in serialized

    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        assert project.phase == 2
        assert project.status == "proposal_pending"


def test_proposal_requires_task_map(app):
    with app.app_context():
        seed_all()
        from app.extensions import db

        project = Project(
            name="无任务项目",
            client_name="测试客户",
            country="TH",
            industry="manufacturing",
            entry_mode="greenfield",
        )
        db.session.add(project)
        db.session.commit()
        project_id = project.id

    client, headers = _client(app)
    response = client.post(
        f"/api/projects/{project_id}/proposals", headers=headers
    )
    assert response.status_code == 400
    assert "任务地图" in response.get_json()["message"]


def test_proposal_workflow_revision_and_confirmation(app):
    project_id = _setup(app)
    client, headers = _client(app)

    first = _generate(client, headers, project_id)
    proposal_id = first["id"]

    early_send = client.post(
        f"/api/proposals/{proposal_id}/send", headers=headers
    )
    assert early_send.status_code == 409

    reviewed = client.post(
        f"/api/proposals/{proposal_id}/review", headers=headers
    )
    assert reviewed.get_json()["data"]["status"] == "pm_reviewed"

    sent = client.post(f"/api/proposals/{proposal_id}/send", headers=headers)
    assert sent.get_json()["data"]["status"] == "sent"

    token = client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "client", "subject_id": "client-a"},
        headers=headers,
    ).get_json()["data"]["token"]

    link = client.get(f"/api/link/{token}/proposal")
    assert link.status_code == 200

    revision = client.post(
        f"/api/link/{token}/proposal/revision",
        json={"note": "请补充预算假设"},
    )
    assert revision.status_code == 200
    assert revision.get_json()["data"]["status"] == "revision_requested"
    assert revision.get_json()["data"]["client_note"] == "请补充预算假设"

    second = _generate(client, headers, project_id)
    assert second["version"] == 2
    second_id = second["id"]
    client.post(f"/api/proposals/{second_id}/review", headers=headers)
    client.post(f"/api/proposals/{second_id}/send", headers=headers)

    confirmed = client.post(f"/api/link/{token}/proposal/confirm")
    assert confirmed.status_code == 200
    data = confirmed.get_json()["data"]
    assert data["status"] == "client_confirmed"
    confirmed_at = data["client_confirmed_at"]
    assert confirmed_at

    repeated = client.post(f"/api/link/{token}/proposal/confirm")
    assert repeated.get_json()["data"]["client_confirmed_at"] == confirmed_at

    with app.app_context():
        project = Project.query.filter_by(id=project_id).first()
        assert project.phase == 3
        assert project.status == "service_selecting"


def test_proposal_versions_list_and_lawyer_forbidden(app):
    project_id = _setup(app)
    client, headers = _client(app)

    _generate(client, headers, project_id)
    _generate(client, headers, project_id)
    listing = client.get(
        f"/api/projects/{project_id}/proposals", headers=headers
    ).get_json()["data"]
    assert [item["version"] for item in listing] == [2, 1]

    lawyer = app.test_client()
    lawyer_headers = bearer(login_token(lawyer, email="lawyer@demo.local"))
    forbidden = lawyer.post(
        f"/api/projects/{project_id}/proposals", headers=lawyer_headers
    )
    assert forbidden.status_code == 403


def test_proposal_link_rejects_provider_token(app):
    project_id = _setup(app)
    client, headers = _client(app)
    proposal = _generate(client, headers, project_id)
    client.post(f"/api/proposals/{proposal['id']}/review", headers=headers)
    client.post(f"/api/proposals/{proposal['id']}/send", headers=headers)

    provider_token = client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "provider"},
        headers=headers,
    ).get_json()["data"]["token"]

    response = client.get(f"/api/link/{provider_token}/proposal")
    assert response.status_code == 403

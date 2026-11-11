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


def test_service_catalog_and_dependency_warnings(app):
    project_id = _setup(app)
    client, headers = _client(app)

    catalog = client.get(
        f"/api/projects/{project_id}/service-catalog", headers=headers
    ).get_json()["data"]
    assert len(catalog["stages"]) == 9
    assert sum(len(stage["items"]) for stage in catalog["stages"]) == 30
    assert catalog["selection"]["codes"] == []

    saved = client.post(
        f"/api/projects/{project_id}/selection",
        json={"codes": ["T16", "T20"], "override_reason": "客户口头选择"},
        headers=headers,
    )
    assert saved.status_code == 200
    payload = saved.get_json()["data"]
    assert payload["selection"]["source"] == "pm"
    assert payload["selection"]["override_reason"] == "客户口头选择"
    missing = {item["missing"] for item in payload["warnings"]}
    assert {"T14", "T11"} & missing


def test_pm_selection_requires_reason_and_client_link_works(app):
    project_id = _setup(app)
    client, headers = _client(app)

    missing_reason = client.post(
        f"/api/projects/{project_id}/selection",
        json={"codes": ["T11"]},
        headers=headers,
    )
    assert missing_reason.status_code == 400

    token = _client_token(client, headers, project_id)
    link = client.get(f"/api/link/{token}/selection")
    assert link.status_code == 200

    saved = client.post(
        f"/api/link/{token}/selection",
        json={"codes": ["T11", "T14"]},
    )
    assert saved.status_code == 200
    assert saved.get_json()["data"]["selection"]["source"] == "client"

    provider_token = client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "provider"},
        headers=headers,
    ).get_json()["data"]["token"]
    forbidden = client.get(f"/api/link/{provider_token}/selection")
    assert forbidden.status_code == 403


def test_generate_candidates_five_per_task_and_reject(app):
    project_id = _setup(app)
    client, headers = _client(app)
    codes = ["T11", "T14", "T16", "T20", "T21"]

    client.post(
        f"/api/projects/{project_id}/selection",
        json={"codes": codes, "override_reason": "演示选择"},
        headers=headers,
    )
    generated = client.post(
        f"/api/projects/{project_id}/candidates/generate",
        json={"task_codes": codes},
        headers=headers,
    )
    assert generated.status_code == 200
    groups = generated.get_json()["data"]
    assert len(groups) == 5
    for group in groups:
        assert len(group["candidates"]) == 5
        assert group["candidates"][0]["match_score"] >= group["candidates"][-1]["match_score"]

    candidates = [row for group in groups for row in group["candidates"]]
    assert any(row["source_type"] == "新发现" for row in candidates)

    target = candidates[0]
    rejected = client.post(
        f"/api/candidates/{target['id']}/reject",
        json={"reason": "利益冲突"},
        headers=headers,
    )
    assert rejected.status_code == 200

    listed = client.get(
        f"/api/projects/{project_id}/candidates", headers=headers
    ).get_json()["data"]
    updated = next(
        row
        for group in listed
        for row in group["candidates"]
        if row["id"] == target["id"]
    )
    assert updated["status"] == "rejected"
    assert updated["reject_reason"] == "利益冲突"


def test_manual_add_candidate_and_generate_requires_selection(app):
    project_id = _setup(app)
    client, headers = _client(app)

    no_selection = client.post(
        f"/api/projects/{project_id}/candidates/generate",
        json={},
        headers=headers,
    )
    assert no_selection.status_code == 400

    providers = client.get("/api/providers", headers=headers).get_json()["data"]
    provider = providers[0]
    added = client.post(
        f"/api/projects/{project_id}/candidates",
        json={
            "task_code": "T11",
            "provider_id": provider["id"],
            "reason": "客户指定",
        },
        headers=headers,
    )
    assert added.status_code == 201
    assert added.get_json()["data"]["provider_name"] == provider["name"]

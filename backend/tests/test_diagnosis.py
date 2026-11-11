from app.models import Fact, Project
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _setup(app):
    with app.app_context():
        seed_all()
        return Project.query.filter_by(name="泰国春武里汽车零部件工厂").first().id


def _client(app):
    client = app.test_client()
    return client, bearer(login_token(client))


def _conversation(client, headers, project_id):
    return client.post(
        f"/api/projects/{project_id}/conversations", json={}, headers=headers
    ).get_json()["data"]["id"]


def test_extract_facts_with_citations_is_idempotent(app):
    project_id = _setup(app)
    client, headers = _client(app)

    first = client.post(
        f"/api/projects/{project_id}/facts/extract", headers=headers
    )
    assert first.status_code == 200
    payload = first.get_json()["data"]
    assert len(payload["facts"]) == 5
    assert payload["verified"] == 5
    assert all(fact["citation_status"] == "verified" for fact in payload["facts"])
    assert all(fact["citation"]["doc_id"] for fact in payload["facts"])

    second = client.post(
        f"/api/projects/{project_id}/facts/extract", headers=headers
    ).get_json()["data"]
    assert len(second["facts"]) == 5

    with app.app_context():
        assert Fact.query.filter_by(project_id=project_id).count() == 5
        assert all(
            fact.version >= 2
            for fact in Fact.query.filter_by(project_id=project_id).all()
        )


def test_fact_extraction_requires_documents(app):
    _setup(app)
    client, headers = _client(app)

    with app.app_context():
        from app.extensions import db

        project = Project(
            name="无资料项目",
            client_name="测试客户",
            country="TH",
            industry="manufacturing",
            entry_mode="greenfield",
        )
        db.session.add(project)
        db.session.commit()
        project_id = project.id

    response = client.post(
        f"/api/projects/{project_id}/facts/extract", headers=headers
    )
    assert response.status_code == 400


def test_interview_max_five_questions_and_three_rounds(app):
    project_id = _setup(app)
    client, headers = _client(app)
    conversation_id = _conversation(client, headers, project_id)

    for expected_round in (1, 2, 3):
        response = client.post(
            f"/api/projects/{project_id}/interview",
            json={"conversation_id": conversation_id},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data["round"] == expected_round
        assert 0 < len(data["questions"]) <= 5
        priorities = [item["priority"] for item in data["questions"]]
        assert priorities == sorted(priorities)

    fourth = client.post(
        f"/api/projects/{project_id}/interview",
        json={"conversation_id": conversation_id},
        headers=headers,
    )
    assert fourth.status_code == 400
    assert fourth.get_json()["code"] == "round_limit"


def test_interview_unknown_answer_does_not_block(app):
    project_id = _setup(app)
    client, headers = _client(app)

    response = client.post(
        f"/api/projects/{project_id}/interview/answers",
        json={
            "answers": [
                {"question": "是否已确定园区外买地？", "answer": "不知道"},
                {"question": "产品是否面向新能源汽车？", "answer": "以新能源为主"},
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200
    facts = {fact["key"]: fact for fact in response.get_json()["data"]}
    assert facts["是否已确定园区外买地？"]["status"] == "unknown"
    assert facts["产品是否面向新能源汽车？"]["status"] == "assumption"


def test_task_graph_lease_and_land_purchase(app):
    project_id = _setup(app)
    client, headers = _client(app)

    lease = client.post(
        f"/api/projects/{project_id}/tasks/refresh",
        json={"scenario": "lease"},
        headers=headers,
    )
    assert lease.status_code == 200
    lease_data = lease.get_json()["data"]
    assert len(lease_data["tasks"]) == 30
    assert lease_data["diff"]["first_generation"] is True
    path = lease_data["critical_path"]
    for code in ("T14", "T16", "T17", "T18", "T29"):
        assert code in path
    assert path.index("T23") < path.index("T18")

    land = client.post(
        f"/api/projects/{project_id}/tasks/refresh",
        json={"scenario": "land_purchase"},
        headers=headers,
    )
    assert land.status_code == 200
    land_data = land.get_json()["data"]
    assert "T11" in land_data["critical_path"]
    assert land_data["total_days"] >= lease_data["total_days"]

    t14 = next(task for task in land_data["tasks"] if task["code"] == "T14")
    assert "T11" in t14["predecessors"]
    assert "T14" in land_data["diff"]["changed"]

    graph = client.get(
        f"/api/projects/{project_id}/task-graph", headers=headers
    ).get_json()["data"]
    assert graph["scenario"] == "land_purchase"
    assert graph["edges"]


def test_task_graph_supports_external_tasks_and_rejects_cycles(app):
    project_id = _setup(app)
    client, headers = _client(app)

    response = client.post(
        f"/api/projects/{project_id}/tasks/refresh",
        json={
            "scenario": "lease",
            "extra_tasks": [
                {
                    "code": "T99",
                    "name": "补充尽调",
                    "stage_no": 0,
                    "duration_days": 10,
                    "predecessors": ["T01"]
                }
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200
    task = next(
        item for item in response.get_json()["data"]["tasks"] if item["code"] == "T99"
    )
    assert task["is_external"] is True

    cycle = client.post(
        f"/api/projects/{project_id}/tasks/refresh",
        json={
            "scenario": "lease",
            "extra_tasks": [
                {"code": "X1", "name": "循环一", "predecessors": ["X2"]},
                {"code": "X2", "name": "循环二", "predecessors": ["X1"]}
            ]
        },
        headers=headers,
    )
    assert cycle.status_code == 400
    assert cycle.get_json()["code"] == "dependency_error"


def test_requirement_generation_and_client_confirmation(app):
    project_id = _setup(app)
    client, headers = _client(app)

    missing = client.get(
        f"/api/projects/{project_id}/requirement", headers=headers
    )
    assert missing.status_code == 404

    generated = client.post(
        f"/api/projects/{project_id}/requirement", headers=headers
    )
    assert generated.status_code == 200
    requirement = generated.get_json()["data"]
    assert requirement["title"] == "需求确认书"
    assert len(requirement["facts"]) == 5
    assert requirement["task_summary"]["total"] == 30
    assert requirement["confirmed_at"] is None

    token = client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "client", "subject_id": "client-a"},
        headers=headers,
    ).get_json()["data"]["token"]

    link = client.get(f"/api/link/{token}/requirement")
    assert link.status_code == 200

    first = client.post(f"/api/link/{token}/requirement/confirm")
    assert first.status_code == 200
    confirmed_at = first.get_json()["data"]["confirmed_at"]
    assert confirmed_at

    second = client.post(f"/api/link/{token}/requirement/confirm")
    assert second.get_json()["data"]["confirmed_at"] == confirmed_at


def test_requirement_link_rejects_provider_token(app):
    project_id = _setup(app)
    client, headers = _client(app)
    client.post(f"/api/projects/{project_id}/requirement", headers=headers)

    provider_token = client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "provider"},
        headers=headers,
    ).get_json()["data"]["token"]

    response = client.get(f"/api/link/{provider_token}/requirement")
    assert response.status_code == 403

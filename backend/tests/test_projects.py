from app.models import Project
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _client(app, email="client@demo.local"):
    client = app.test_client()
    return client, bearer(login_token(client, email=email))


def _payload(**overrides):
    data = {
        "country": "TH",
        "industry": "manufacturing",
        "entry_mode": "greenfield",
        "currency": "USD",
        "investment_cents": 30_000_000,
        "goal_text": "计划在泰国设厂。",
    }
    data.update(overrides)
    return data


def test_client_creates_project_and_sees_only_own(app):
    with app.app_context():
        seed_all()

    client, headers = _client(app)
    created = client.post("/api/projects", json=_payload(), headers=headers)
    assert created.status_code == 201, created.get_json()
    project = created.get_json()["data"]
    assert project["client_name"] == "长三角民营汽车零部件制造企业"
    assert project["phase"] == 1

    listing = client.get("/api/projects", headers=headers).get_json()["data"]
    ids = {row["id"] for row in listing}
    assert project["id"] in ids
    assert len(listing) == 3

    pm_client, pm_headers = _client(app, "pm@demo.local")
    pm_listing = pm_client.get("/api/projects", headers=pm_headers).get_json()["data"]
    assert len(pm_listing) == 3


def test_client_cannot_access_pm_created_project(app):
    with app.app_context():
        seed_all()

    pm_client, pm_headers = _client(app, "pm@demo.local")
    pm_project = pm_client.post(
        "/api/projects",
        json=_payload(client_name="其他客户"),
        headers=pm_headers,
    ).get_json()["data"]

    client, headers = _client(app)
    response = client.get(f"/api/projects/{pm_project['id']}", headers=headers)
    assert response.status_code == 403

    listing = client.get("/api/projects", headers=headers).get_json()["data"]
    assert pm_project["id"] not in {row["id"] for row in listing}


def test_pm_project_creation_requires_client_name(app):
    with app.app_context():
        seed_all()

    pm_client, pm_headers = _client(app, "pm@demo.local")
    response = pm_client.post("/api/projects", json=_payload(), headers=pm_headers)
    assert response.status_code == 400


def test_client_cannot_run_internal_ai_steps_but_can_select_services(app):
    with app.app_context():
        seed_all()
        project_id = Project.query.first().id

    client, headers = _client(app)
    blocked = client.post(
        f"/api/projects/{project_id}/facts/extract", headers=headers
    )
    assert blocked.status_code == 403

    selected = client.post(
        f"/api/projects/{project_id}/selection",
        json={"codes": ["T11"]},
        headers=headers,
    )
    assert selected.status_code == 200
    payload = selected.get_json()["data"]
    assert payload["selection"]["source"] == "client"
    assert payload["selection"]["codes"] == ["T11"]

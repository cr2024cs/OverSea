from datetime import date, timedelta

from app.extensions import db
from app.models import Contract, Milestone, Project, Provider, Task, User
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _login(app, email):
    client = app.test_client()
    return client, bearer(login_token(client, email=email))


def test_provider_workbench_and_quote(app):
    with app.app_context():
        seed_all()

    client, headers = _login(app, "provider@demo.local")
    workbench = client.get("/api/provider/workbench", headers=headers)
    assert workbench.status_code == 200
    data = workbench.get_json()["data"]
    assert data["provider"]["name"]
    assert data["rfps"]
    rfp = data["rfps"][0]

    submitted = client.post(
        f"/api/provider/rfps/{rfp['id']}/quote",
        json={"amount_cents": 45_000_000, "currency": "CNY"},
        headers=headers,
    )
    assert submitted.status_code == 201
    assert submitted.get_json()["data"]["amount_cents"] == 45_000_000


def test_expert_account_review(app):
    with app.app_context():
        seed_all()
        project = Project.query.first()
        task = Task.query.filter_by(project_id=project.id, code="T11").first()
        provider = Provider.query.first()
        expert = User.query.filter_by(email="expert@demo.local").first()
        milestone = Milestone(
            project_id=project.id,
            task_id=task.id,
            provider_id=provider.id,
            expert_user_id=expert.id,
            name=task.name,
            due_date=date.today() + timedelta(days=2),
            status="expert_review",
        )
        db.session.add(milestone)
        db.session.commit()
        milestone_id = milestone.id

    client, headers = _login(app, "expert@demo.local")
    workbench = client.get("/api/expert/workbench", headers=headers)
    assert workbench.status_code == 200
    assert workbench.get_json()["data"][0]["milestone_id"] == milestone_id

    detail = client.get(f"/api/expert/milestones/{milestone_id}", headers=headers)
    assert "provider_name" not in detail.get_json()["data"]

    reviewed = client.post(
        f"/api/expert/milestones/{milestone_id}/review",
        json={
            "scores": {
                "completeness": 85,
                "quality": 80,
                "executability": 75,
                "timeliness": 90,
            },
            "comment": "符合要求。",
            "conflict_declared": True,
        },
        headers=headers,
    )
    assert reviewed.status_code == 200

    repeat = client.post(
        f"/api/expert/milestones/{milestone_id}/review",
        json={
            "scores": {
                "completeness": 85,
                "quality": 80,
                "executability": 75,
                "timeliness": 90,
            },
            "comment": "重复",
            "conflict_declared": True,
        },
        headers=headers,
    )
    assert repeat.status_code == 409


def test_client_portal_requirement_confirmation(app):
    with app.app_context():
        seed_all()
        project_id = Project.query.first().id

    pm_client, pm_headers = _login(app, "pm@demo.local")
    pm_client.post(
        f"/api/projects/{project_id}/requirement", headers=pm_headers
    )

    client, headers = _login(app, "client@demo.local")
    portal = client.get(
        f"/api/projects/{project_id}/client-portal", headers=headers
    )
    assert portal.status_code == 200
    data = portal.get_json()["data"]
    assert data["requirement"]
    assert data["requirement"]["confirmed_at"] is None

    confirmed = client.post(
        f"/api/projects/{project_id}/client-portal/requirement/confirm",
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.get_json()["data"]["confirmed_at"]

    with app.app_context():
        project = db.session.get(Project, project_id)
        assert project.requirement_confirmed_at is not None

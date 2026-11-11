from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import Milestone, Project, Provider, Task
from app.seeds.seed import seed_all
from app.services.task_graph import compute_schedule
from app.services.tokens import issue_access_token
from tests.helpers import bearer, login_token


def test_critical_path_calculation():
    tasks = [
        {"code": "A", "duration_days": 10, "predecessors": []},
        {"code": "B", "duration_days": 20, "predecessors": ["A"]},
        {"code": "C", "duration_days": 5, "predecessors": ["A"]},
        {"code": "D", "duration_days": 1, "predecessors": ["B"]},
    ]
    schedule = compute_schedule(tasks)
    assert schedule["total_days"] == 31
    assert schedule["critical_path"] == ["A", "B", "D"]


def test_cycle_is_rejected():
    tasks = [
        {"code": "X", "duration_days": 1, "predecessors": ["Y"]},
        {"code": "Y", "duration_days": 1, "predecessors": ["X"]},
    ]
    with pytest.raises(ValueError):
        compute_schedule(tasks)


def test_client_quote_fee_and_total(app):
    with app.app_context():
        seed_all()
        project = Project.query.first()
        project.phase = 3
        project.status = "service_selecting"
        db.session.commit()
        project_id = project.id

    client = app.test_client()
    headers = bearer(login_token(client))
    response = client.post(
        f"/api/projects/{project_id}/client-quotes",
        json={
            "provider_amount_cents": 40_000_000,
            "lawyer_amount_cents": 1_000_000,
            "management_fee_rate": 0.175,
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["management_fee_cents"] == 7_000_000
    assert data["total_cents"] == 48_000_000
    assert data["fee_percent"] == 14.58


def test_expert_weighted_score(app):
    with app.app_context():
        seed_all()
        project = Project.query.first()
        task = Task.query.filter_by(project_id=project.id, code="T11").first()
        provider = Provider.query.first()
        milestone = Milestone(
            project_id=project.id,
            task_id=task.id,
            provider_id=provider.id,
            name=task.name,
            due_date=date.today() + timedelta(days=2),
            status="expert_review",
        )
        db.session.add(milestone)
        db.session.commit()
        milestone_id = milestone.id
        token, _row = issue_access_token(
            project_id=project.id,
            role_type="expert",
            subject_id=milestone.id,
        )
        db.session.commit()

    client = app.test_client()
    response = client.post(
        f"/api/link/{token}/expert/review",
        json={
            "scores": {
                "completeness": 90,
                "quality": 80,
                "executability": 70,
                "timeliness": 60,
            },
            "comment": "加权评分测试",
            "conflict_declared": True,
        },
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["total"] == 79.0

import json
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import (
    Finding,
    Milestone,
    Project,
    Provider,
    QueryLetter,
    Task,
)
from app.seeds.seed import seed_all
from app.services.review import classify_conclusion
from app.services.tokens import issue_access_token
from tests.helpers import bearer, login_token


def _setup(app):
    with app.app_context():
        seed_all()
        project = Project.query.filter_by(name="泰国春武里汽车零部件工厂").first()
        task = Task.query.filter_by(project_id=project.id, code="T11").first()
        provider = Provider.query.first()
        milestone = Milestone(
            project_id=project.id,
            task_id=task.id,
            provider_id=provider.id,
            name=task.name,
            due_date=date.today() + timedelta(days=2),
            status="expert_review",
            acceptor_type="expert",
        )
        db.session.add(milestone)
        db.session.commit()
        return project.id, task.id, provider.id, milestone.id


def _client(app):
    client = app.test_client()
    return client, bearer(login_token(client))


def test_legal_query_requires_lawyer_approval(app):
    project_id, _task_id, _provider_id, _milestone_id = _setup(app)
    client, headers = _client(app)

    with app.app_context():
        finding = Finding.query.filter_by(project_id=project_id).first()
        letter = QueryLetter(
            project_id=project_id,
            provider_id=Provider.query.first().id,
            finding_ids_json=[finding.id],
            content="法律类质询",
            approval_status="pending",
            status="draft",
        )
        db.session.add(letter)
        db.session.commit()
        letter_id = letter.id

    response = client.post(f"/api/query-letters/{letter_id}/send", headers=headers)
    assert response.status_code == 403
    assert "律师" in response.get_json()["message"]


def test_verified_error_requires_clickable_source():
    assert (
        classify_conclusion("verified_error", [], citation_verified=True)
        == "needs_verification"
    )
    assert (
        classify_conclusion(
            "verified_error", [{"clickable": True}], citation_verified=True
        )
        == "verified_error"
    )


def test_failed_node_does_not_unlock_dependents(app):
    project_id, _task_id, _provider_id, milestone_id = _setup(app)
    client, headers = _client(app)

    with app.app_context():
        milestone = db.session.get(Milestone, milestone_id)
        milestone.expert_locked = True
        milestone.expert_total = 50
        db.session.commit()

    response = client.post(
        f"/api/milestones/{milestone_id}/finalize", headers=headers
    )
    assert response.get_json()["data"]["status"] == "failed"

    with app.app_context():
        blocked = Task.query.filter_by(project_id=project_id, code="T12").first()
        assert blocked.locked is True


def test_expert_payload_is_blind(app):
    project_id, _task_id, provider_id, milestone_id = _setup(app)
    client, headers = _client(app)

    invite = client.post(
        f"/api/milestones/{milestone_id}/expert-invite", headers=headers
    )
    token = invite.get_json()["data"]["token"]
    payload = client.get(f"/api/link/{token}/expert").get_json()["data"]

    serialized = json.dumps(payload, ensure_ascii=False)
    assert "provider_name" not in payload
    assert "provider_id" not in payload
    assert "price" not in serialized
    assert "quote" not in serialized
    assert "pm_review_note" not in payload


def test_only_configured_options_are_offered(app):
    with app.app_context():
        seed_all()

    client = app.test_client()
    headers = bearer(login_token(client))
    data = client.get("/api/config", headers=headers).get_json()["data"]
    assert [item["code"] for item in data["country"]] == ["TH"]
    assert [item["code"] for item in data["industry"]] == ["manufacturing"]
    assert [item["code"] for item in data["entry_mode"]] == ["greenfield"]

from datetime import date, timedelta

from app.extensions import db
from app.models import Finding, Milestone, PerformanceEvent, Project, Provider, Task
from app.seeds.seed import seed_all
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
            deliverable="BOI 批复函与证书",
            acceptance_criteria="活动类别与条件说明完整",
            due_date=date.today() + timedelta(days=5),
            status="pending_submission",
            acceptor_type="expert",
            grace_days=3,
        )
        db.session.add(milestone)
        db.session.commit()
        return project.id, task.id, provider.id, milestone.id


def _client(app):
    client = app.test_client()
    return client, bearer(login_token(client))


def _provider_token(client, headers, project_id, provider_id):
    return client.post(
        "/api/access-tokens",
        json={
            "project_id": project_id,
            "role_type": "provider",
            "subject_id": provider_id,
        },
        headers=headers,
    ).get_json()["data"]["token"]


def test_board_and_submission_flow(app):
    project_id, _task_id, provider_id, milestone_id = _setup(app)
    client, headers = _client(app)

    board = client.get(f"/api/projects/{project_id}/board", headers=headers)
    assert board.status_code == 200
    data = board.get_json()["data"]
    assert data["total"] >= 1
    assert data["milestones"][0]["reminder_level"] in {1, 3, 7, 0}

    submitted = client.post(
        f"/api/milestones/{milestone_id}/submission",
        json={"note": "服务商答复：BOI 项目原则上可以获得优惠。", "files": ["boi.pdf"]},
        headers=headers,
    )
    assert submitted.status_code == 200
    assert submitted.get_json()["data"]["status"] == "submitted"

    returned = client.post(
        f"/api/milestones/{milestone_id}/pm-review",
        json={"decision": "return", "note": "缺少活动类别"},
        headers=headers,
    )
    assert returned.get_json()["data"]["status"] == "pending_submission"

    client.post(
        f"/api/milestones/{milestone_id}/submission",
        json={"note": "补充活动类别后的答复。"},
        headers=headers,
    )
    accepted = client.post(
        f"/api/milestones/{milestone_id}/pm-review",
        json={"decision": "accept"},
        headers=headers,
    )
    assert accepted.get_json()["data"]["status"] == "expert_review"

    provider_token = _provider_token(client, headers, project_id, provider_id)
    provider_submission = client.post(
        f"/api/link/{provider_token}/milestone/{milestone_id}/submission",
        json={"note": "服务商通过链接提交的交付物"},
    )
    assert provider_submission.status_code == 200
    assert provider_submission.get_json()["data"]["submission_note"].startswith("服务商通过链接")


def test_ai_review_and_query_letter_approval_gate(app):
    project_id, _task_id, provider_id, milestone_id = _setup(app)
    client, headers = _client(app)

    client.post(
        f"/api/milestones/{milestone_id}/submission",
        json={"note": "服务商答复：二手设备都可以免税进口。"},
        headers=headers,
    )
    reviewed = client.post(
        f"/api/milestones/{milestone_id}/review", json={}, headers=headers
    )
    assert reviewed.status_code == 200
    findings = reviewed.get_json()["data"]
    assert len(findings) == 8
    assert all(item["citation_status"] == "verified" for item in findings)

    with app.app_context():
        assert Finding.query.filter_by(milestone_id=milestone_id).count() == 8

    letter = client.post(
        f"/api/projects/{project_id}/query-letters",
        json={"milestone_id": milestone_id, "provider_id": provider_id},
        headers=headers,
    )
    assert letter.status_code == 201
    letter_data = letter.get_json()["data"]
    assert letter_data["approval_status"] == "pending"
    finding_ids = [item["id"] for item in letter_data["findings"]]
    assert len(finding_ids) >= 8

    early_send = client.post(
        f"/api/query-letters/{letter_data['id']}/send", headers=headers
    )
    assert early_send.status_code == 403

    lawyer = app.test_client()
    lawyer_headers = bearer(login_token(lawyer, email="lawyer@demo.local"))
    approved = lawyer.post(
        f"/api/query-letters/{letter_data['id']}/approve", headers=lawyer_headers
    )
    assert approved.get_json()["data"]["approval_status"] == "approved"

    sent = client.post(
        f"/api/query-letters/{letter_data['id']}/send", headers=headers
    )
    assert sent.get_json()["data"]["status"] == "sent"

    provider_token = _provider_token(client, headers, project_id, provider_id)
    link = client.get(f"/api/link/{provider_token}/query-letter")
    assert link.status_code == 200

    replies = [
        {"finding_id": finding_id, "reply": "已补充说明"}
        for finding_id in finding_ids
    ]
    replied = client.post(
        f"/api/link/{provider_token}/query-letter/reply",
        json={"replies": replies},
    )
    assert replied.get_json()["data"]["status"] == "replied"

    closed = client.post(
        f"/api/query-letters/{letter_data['id']}/close", headers=headers
    )
    assert closed.get_json()["data"]["status"] == "closed"


def test_expert_blind_review_lock_and_finalize_unlock(app):
    project_id, _task_id, provider_id, milestone_id = _setup(app)
    client, headers = _client(app)

    client.post(
        f"/api/milestones/{milestone_id}/submission",
        json={"note": "完整交付物"},
        headers=headers,
    )
    client.post(
        f"/api/milestones/{milestone_id}/pm-review",
        json={"decision": "accept"},
        headers=headers,
    )

    invite = client.post(
        f"/api/milestones/{milestone_id}/expert-invite", headers=headers
    )
    assert invite.status_code == 201
    expert_token = invite.get_json()["data"]["token"]

    view = client.get(f"/api/link/{expert_token}/expert")
    assert view.status_code == 200
    payload = view.get_json()["data"]
    assert "provider_name" not in payload
    assert "price" not in json_text(payload)
    assert payload["locked"] is False

    scores = {
        "completeness": 90,
        "quality": 90,
        "executability": 90,
        "timeliness": 90,
    }
    reviewed = client.post(
        f"/api/link/{expert_token}/expert/review",
        json={
            "scores": scores,
            "comment": "交付完整，可执行。",
            "conflict_declared": True,
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.get_json()["data"]["total"] == 90

    repeat = client.post(
        f"/api/link/{expert_token}/expert/review",
        json={
            "scores": scores,
            "comment": "重复",
            "conflict_declared": True,
        },
    )
    assert repeat.status_code == 409

    with app.app_context():
        t12 = Task.query.filter_by(project_id=project_id, code="T12").first()
        assert t12.locked is True

    finalized = client.post(
        f"/api/milestones/{milestone_id}/finalize", headers=headers
    )
    assert finalized.status_code == 200
    result = finalized.get_json()["data"]
    assert result["status"] == "passed"
    assert "T12" in result["unlocked_tasks"]

    with app.app_context():
        t12 = Task.query.filter_by(project_id=project_id, code="T12").first()
        assert t12.locked is False
        event = PerformanceEvent.query.filter_by(milestone_id=milestone_id).first()
        assert event is not None

    score = client.get(f"/api/providers/{provider_id}/score", headers=headers)
    assert score.status_code == 200
    assert score.get_json()["data"]["data_sufficient"] is True


def test_failed_acceptance_keeps_dependents_locked_and_allows_rectification(app):
    project_id, _task_id, _provider_id, milestone_id = _setup(app)
    client, headers = _client(app)

    with app.app_context():
        milestone = db.session.get(Milestone, milestone_id)
        milestone.expert_locked = True
        milestone.expert_total = 50
        milestone.status = "client_confirm"
        db.session.commit()

    finalized = client.post(
        f"/api/milestones/{milestone_id}/finalize", headers=headers
    )
    assert finalized.get_json()["data"]["status"] == "failed"
    assert finalized.get_json()["data"]["rounds"] == 1

    with app.app_context():
        t12 = Task.query.filter_by(project_id=project_id, code="T12").first()
        assert t12.locked is True

    rectified = client.post(
        f"/api/milestones/{milestone_id}/rectify", headers=headers
    )
    assert rectified.get_json()["data"]["status"] == "pending_submission"


def json_text(payload):
    import json

    return json.dumps(payload, ensure_ascii=False)

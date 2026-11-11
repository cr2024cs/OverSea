import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from app.extensions import db
from app.models import Archive, Finding, Milestone, Project, Provider, QueryLetter, Task
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _setup(app):
    with app.app_context():
        seed_all()
        return Project.query.filter_by(name="泰国春武里汽车零部件工厂").first().id


def _client(app):
    client = app.test_client()
    return client, bearer(login_token(client))


def _close_findings(project_id):
    for row in Finding.query.filter_by(project_id=project_id).all():
        row.closed_at = datetime.utcnow()
        row.reply_text = row.reply_text or "已回复"
    db.session.commit()


def _make_passed_milestone(project_id, code="T11", confirmed=True):
    task = Task.query.filter_by(project_id=project_id, code=code).first()
    provider = Provider.query.first()
    milestone = Milestone(
        project_id=project_id,
        task_id=task.id,
        provider_id=provider.id,
        name=task.name,
        deliverable="交付物",
        acceptance_criteria="验收标准",
        due_date=date.today() + timedelta(days=2),
        status="passed",
        acceptor_type="pm",
        expert_total=90,
        expert_locked=True,
        expert_submitted_at=datetime.utcnow(),
        client_confirmed_at=datetime.utcnow() if confirmed else None,
    )
    db.session.add(milestone)
    db.session.commit()
    return milestone.id


def test_retrospective_benchmark_and_metrics(app):
    project_id = _setup(app)
    client, headers = _client(app)

    retrospective = client.post(
        f"/api/projects/{project_id}/retrospective", headers=headers
    )
    assert retrospective.status_code == 200
    payload = retrospective.get_json()["data"]
    assert "timeline" in payload
    assert "budget" in payload
    assert "issues" in payload

    benchmark = client.get(
        "/api/benchmarks", query_string={"country": "TH", "task_code": "T11"}, headers=headers
    )
    rows = benchmark.get_json()["data"]
    assert rows
    assert rows[0]["sample_count"] == 2
    assert rows[0]["min_cents"] == 12_000_000
    assert rows[0]["data_sufficient"] is False

    with app.app_context():
        project_id = Project.query.first().id
        _make_passed_milestone(project_id)
        findings = Finding.query.filter_by(project_id=project_id).limit(4).all()
        for row in findings:
            row.closed_at = datetime.utcnow()
        db.session.commit()

    metrics = client.get(
        f"/api/projects/{project_id}/metrics", headers=headers
    ).get_json()["data"]
    with app.app_context():
        major = Finding.query.filter_by(project_id=project_id, severity="重大").all()
        expected_major_rate = round(
            len([row for row in major if row.closed_at]) / len(major) * 100, 2
        )
    assert metrics["effective_query_rate"]["value"] == 50.0
    assert metrics["major_close_rate"]["value"] == expected_major_rate
    assert metrics["milestone_on_time_rate"]["value"] == 100.0
    assert metrics["effective_match_rate"]["value"] is None
    assert metrics["acceptance_rate"]["value"] is None


def test_archive_creation_download_and_readonly(app):
    project_id = _setup(app)
    client, headers = _client(app)

    with app.app_context():
        _close_findings(project_id)
        _make_passed_milestone(project_id, "T11")
        _make_passed_milestone(project_id, "T12")
        project = db.session.get(Project, project_id)
        project.phase = 6
        project.status = "executing"
        db.session.commit()

    created = client.post(
        f"/api/projects/{project_id}/archives", headers=headers
    )
    assert created.status_code == 201, created.get_json()
    archive = created.get_json()["data"]
    assert archive["version"] == 1
    assert len(archive["file_hash"]) == 64
    assert archive["manifest"]["files"]

    with app.app_context():
        row = Archive.query.filter_by(project_id=project_id).first()
        assert row is not None
        path = Path(row.zip_path)
        assert path.exists()
        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
        assert "manifest.json" in names
        assert "proposals.json" in names
        project = db.session.get(Project, project_id)
        assert project.archived is True
        assert project.status == "closed"

    listing = client.get(
        f"/api/projects/{project_id}/archives", headers=headers
    ).get_json()["data"]
    assert len(listing) == 1

    download = client.get(
        f"/api/archives/{archive['id']}/download", headers=headers
    )
    assert download.status_code == 200
    assert download.data[:2] == b"PK"

    blocked = client.post(
        f"/api/milestones/{_milestone_id(app, project_id)}/submission",
        json={"note": "after archive"},
        headers=headers,
    )
    assert blocked.status_code == 409
    assert blocked.get_json()["code"] == "project_archived"


def _milestone_id(app, project_id):
    with app.app_context():
        return Milestone.query.filter_by(project_id=project_id).first().id


def test_archive_blocks_incomplete_project(app):
    project_id = _setup(app)
    client, headers = _client(app)

    no_milestone = client.post(
        f"/api/projects/{project_id}/archives", headers=headers
    )
    assert no_milestone.status_code == 400
    assert "节点" in no_milestone.get_json()["message"]

    with app.app_context():
        _make_passed_milestone(project_id, "T11")

    open_findings = client.post(
        f"/api/projects/{project_id}/archives", headers=headers
    )
    assert open_findings.status_code == 400
    assert "重大发现" in open_findings.get_json()["message"]

    with app.app_context():
        _close_findings(project_id)
        milestone = Milestone.query.filter_by(project_id=project_id).first()
        milestone.client_confirmed_at = None
        db.session.commit()

    unconfirmed = client.post(
        f"/api/projects/{project_id}/archives", headers=headers
    )
    assert unconfirmed.status_code == 400
    assert "客户确认" in unconfirmed.get_json()["message"]


def test_closed_qa_and_admin_reset(app):
    project_id = _setup(app)
    client, headers = _client(app)
    admin = app.test_client()
    admin_headers = bearer(login_token(admin, email="admin@demo.local"))

    with app.app_context():
        findings = Finding.query.filter_by(project_id=project_id).limit(2).all()
        for row in findings:
            row.reply_text = "已补充"
            row.closed_at = datetime.utcnow()
        letter = QueryLetter(
            project_id=project_id,
            provider_id=Provider.query.first().id,
            finding_ids_json=[row.id for row in findings],
            content="BOI 活动类别质询",
            approval_status="approved",
            approved_by_role="lawyer",
            status="closed",
            closed_at=datetime.utcnow(),
        )
        db.session.add(letter)
        db.session.commit()

    qa = client.get(
        "/api/knowledge/qa", query_string={"q": "BOI"}, headers=headers
    )
    assert qa.status_code == 200
    assert qa.get_json()["data"]

    reset = admin.post("/api/admin/demo/reset", headers=admin_headers)
    assert reset.status_code == 200
    assert reset.get_json()["data"]["projects"] == 2

    with app.app_context():
        assert Archive.query.count() == 1
        project = Project.query.first()
        assert project.archived is False

from app.extensions import db
from app.models import Project, Provider, QueryLetter
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _client(app, email):
    client = app.test_client()
    return client, bearer(login_token(client, email=email))


def test_admin_overview_and_permissions(app):
    with app.app_context():
        seed_all()

    admin, headers = _client(app, "admin@demo.local")
    response = admin.get("/api/admin/overview", headers=headers)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["counts"]["users"] == 6
    assert len(data["users"]) == 6

    pm, pm_headers = _client(app, "pm@demo.local")
    assert pm.get("/api/admin/overview", headers=pm_headers).status_code == 403


def test_lawyer_workbench_lists_pending_queries(app):
    with app.app_context():
        seed_all()
        project = Project.query.first()
        provider = Provider.query.first()
        letter = QueryLetter(
            project_id=project.id,
            provider_id=provider.id,
            finding_ids_json=[],
            content="待审批质询",
            approval_status="pending",
            status="draft",
        )
        db.session.add(letter)
        db.session.commit()
        letter_id = letter.id

    lawyer, headers = _client(app, "lawyer@demo.local")
    response = lawyer.get("/api/lawyer/workbench", headers=headers)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert any(item["id"] == letter_id for item in data["pending_letters"])
    assert data["projects"]

    pm, pm_headers = _client(app, "pm@demo.local")
    assert pm.get("/api/lawyer/workbench", headers=pm_headers).status_code == 403


def test_project_list_has_investment_and_client_scope(app):
    with app.app_context():
        seed_all()

    client, headers = _client(app, "client@demo.local")
    rows = client.get("/api/projects", headers=headers).get_json()["data"]
    assert rows
    assert "investment_cents" in rows[0]
    assert "updated_at" in rows[0]

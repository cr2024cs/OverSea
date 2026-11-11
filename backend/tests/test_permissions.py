import pytest

from app.extensions import db
from app.models import Project, User
from app.seeds.seed import seed_all
from app.services.permissions import (
    can_approve_query_letter,
    can_edit_quote,
    ensure_project_scope,
)
from app.services.tokens import issue_access_token
from tests.helpers import bearer, login_token


def _demo_project(app):
    return Project.query.filter_by(name="泰国春武里汽车零部件工厂").first()


def test_internal_users_can_read_projects(app):
    with app.app_context():
        seed_all()
        project_id = _demo_project(app).id

    client = app.test_client()
    for email in ("pm@demo.local", "lawyer@demo.local", "admin@demo.local"):
        headers = bearer(login_token(client, email=email))
        listing = client.get("/api/projects", headers=headers)
        assert listing.status_code == 200
        detail = client.get(f"/api/projects/{project_id}", headers=headers)
        assert detail.status_code == 200


def test_project_endpoints_require_login(app):
    with app.app_context():
        seed_all()
        project_id = _demo_project(app).id

    client = app.test_client()
    assert client.get("/api/projects").status_code == 401
    assert client.get(f"/api/projects/{project_id}").status_code == 401


def test_missing_project_returns_404(app):
    with app.app_context():
        seed_all()

    client = app.test_client()
    response = client.get("/api/projects/does-not-exist", headers=bearer(login_token(client)))
    assert response.status_code == 404


def test_quote_and_approval_permissions():
    with_app_user = {
        "pm": User(role="pm", active=True),
        "lawyer": User(role="lawyer", active=True),
        "admin": User(role="admin", active=True),
    }
    assert can_edit_quote(with_app_user["pm"]) is True
    assert can_edit_quote(with_app_user["admin"]) is True
    assert can_edit_quote(with_app_user["lawyer"]) is False

    assert can_approve_query_letter(with_app_user["lawyer"]) is True
    assert can_approve_query_letter(with_app_user["admin"]) is False
    assert can_approve_query_letter(with_app_user["pm"]) is False


def test_external_token_scoped_to_project(app):
    with app.app_context():
        seed_all()
        project_a = _demo_project(app)
        project_b = Project(
            name="第二个项目",
            client_name="另一家客户",
            country="TH",
            industry="manufacturing",
            entry_mode="greenfield",
        )
        db.session.add(project_b)
        db.session.commit()
        project_b_id = project_b.id
        raw_token, row = issue_access_token(project_a.id, "client")
        db.session.commit()

        with pytest.raises(PermissionError):
            ensure_project_scope(row, project_b_id)

    client = app.test_client()
    own = client.get(f"/api/link/{raw_token}/project")
    assert own.status_code == 200

    other = client.get(f"/api/link/{raw_token}/projects/{project_b_id}")
    assert other.status_code == 403
    assert other.get_json()["code"] == "forbidden"

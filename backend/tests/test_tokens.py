from datetime import datetime, timedelta

from app.extensions import db
from app.models import AccessToken, Project
from app.seeds.seed import seed_all
from tests.helpers import bearer, login_token


def _project_id(app):
    return Project.query.filter_by(name="泰国春武里汽车零部件工厂").first().id


def _create_token(client, headers, project_id, role_type="client", **extra):
    payload = {"project_id": project_id, "role_type": role_type}
    payload.update(extra)
    return client.post("/api/access-tokens", json=payload, headers=headers)


def test_token_is_hashed_and_usable(app):
    with app.app_context():
        seed_all()
        project_id = _project_id(app)

    client = app.test_client()
    headers = bearer(login_token(client))
    response = _create_token(client, headers, project_id, subject_id="client-a")
    assert response.status_code == 201

    data = response.get_json()["data"]
    raw_token = data["token"]
    assert len(raw_token) >= 32
    assert data["role_type"] == "client"
    assert data["expires_at"]

    with app.app_context():
        row = db.session.get(AccessToken, data["id"])
        assert row.token != raw_token
        assert len(row.token) == 64
        assert row.last_ip is None

    whoami = client.get(f"/api/link/{raw_token}/whoami")
    assert whoami.status_code == 200
    payload = whoami.get_json()["data"]
    assert payload["role_type"] == "client"
    assert payload["project_id"] == project_id
    assert payload["subject_id"] == "client-a"

    with app.app_context():
        row = db.session.get(AccessToken, data["id"])
        assert row.last_ip == "127.0.0.1"
        assert row.last_access_at is not None


def test_revoked_token_rejected(app):
    with app.app_context():
        seed_all()
        project_id = _project_id(app)

    client = app.test_client()
    headers = bearer(login_token(client))
    created = _create_token(client, headers, project_id).get_json()["data"]

    revoke = client.post(
        f"/api/access-tokens/{created['id']}/revoke", headers=headers
    )
    assert revoke.status_code == 200

    response = client.get(f"/api/link/{created['token']}/whoami")
    assert response.status_code == 401
    assert response.get_json()["code"] == "access_token_revoked"


def test_expired_token_rejected(app):
    with app.app_context():
        seed_all()
        project_id = _project_id(app)

    client = app.test_client()
    headers = bearer(login_token(client))
    created = _create_token(client, headers, project_id).get_json()["data"]

    with app.app_context():
        row = db.session.get(AccessToken, created["id"])
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()

    response = client.get(f"/api/link/{created['token']}/whoami")
    assert response.status_code == 401
    assert response.get_json()["code"] == "access_token_expired"


def test_lawyer_cannot_create_token(app):
    with app.app_context():
        seed_all()
        project_id = _project_id(app)

    client = app.test_client()
    headers = bearer(login_token(client, email="lawyer@demo.local"))
    response = _create_token(client, headers, project_id)
    assert response.status_code == 403


def test_invalid_role_type_rejected(app):
    with app.app_context():
        seed_all()
        project_id = _project_id(app)

    client = app.test_client()
    headers = bearer(login_token(client))
    response = _create_token(client, headers, project_id, role_type="admin")
    assert response.status_code == 400

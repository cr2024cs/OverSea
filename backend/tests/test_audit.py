from app.models import AuditLog, Project
from app.seeds.seed import seed_all
from tests.helpers import bearer, login, login_token


def _project_id(app):
    return Project.query.filter_by(name="泰国春武里汽车零部件工厂").first().id


def test_login_writes_audit(app):
    with app.app_context():
        seed_all()

    client = app.test_client()
    login(client)
    login(client, password="wrong-password")

    with app.app_context():
        success = AuditLog.query.filter_by(action="login_success").all()
        failed = AuditLog.query.filter_by(action="login_failed").all()

    assert len(success) == 1
    assert success[0].actor_label == "项目经理"
    assert success[0].ip == "127.0.0.1"
    assert len(failed) == 1
    assert failed[0].actor_label == "pm@demo.local"


def test_token_actions_write_audit(app):
    with app.app_context():
        seed_all()
        project_id = _project_id(app)

    client = app.test_client()
    headers = bearer(login_token(client))
    created = client.post(
        "/api/access-tokens",
        json={"project_id": project_id, "role_type": "provider"},
        headers=headers,
    ).get_json()["data"]

    client.post(f"/api/access-tokens/{created['id']}/revoke", headers=headers)

    with app.app_context():
        create_log = AuditLog.query.filter_by(action="access_token_created").one()
        revoke_log = AuditLog.query.filter_by(action="access_token_revoked").one()

    assert create_log.project_id == project_id
    assert create_log.object_id == created["id"]
    assert create_log.actor_label == "项目经理"
    assert revoke_log.object_id == created["id"]
    assert revoke_log.project_id == project_id

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.models import User
from app.seeds.seed import seed_all
from tests.helpers import bearer, login, login_token


def test_login_and_me(app):
    with app.app_context():
        seed_all()

    client = app.test_client()
    token = login_token(client)

    response = client.get("/api/auth/me", headers=bearer(token))
    assert response.status_code == 200
    user = response.get_json()["data"]
    assert user["email"] == "pm@demo.local"
    assert user["role"] == "pm"
    assert "password_hash" not in user


def test_login_rejects_wrong_password(app):
    with app.app_context():
        seed_all()

    response = login(app.test_client(), password="wrong-password")
    assert response.status_code == 401
    assert response.get_json()["code"] == "invalid_credentials"


def test_me_requires_token(app):
    response = app.test_client().get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["code"] == "unauthorized"


def test_expired_jwt_rejected(app):
    with app.app_context():
        seed_all()
        user = User.query.filter_by(email="pm@demo.local").first()
        payload = {
            "sub": user.id,
            "role": user.role,
            "exp": datetime.now(timezone.utc) - timedelta(seconds=5),
        }
        expired = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

    response = app.test_client().get("/api/auth/me", headers=bearer(expired))
    assert response.status_code == 401
    assert response.get_json()["code"] == "token_expired"


def test_invalid_jwt_rejected(app):
    response = app.test_client().get(
        "/api/auth/me", headers=bearer("not-a-valid-jwt")
    )
    assert response.status_code == 401
    assert response.get_json()["code"] == "invalid_token"

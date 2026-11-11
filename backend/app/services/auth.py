from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app


def create_jwt(user):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=current_app.config["JWT_EXPIRES_HOURS"])
    payload = {
        "sub": user.id,
        "role": user.role,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")
    return token, expires_at


def decode_jwt(token):
    return jwt.decode(
        token,
        current_app.config["SECRET_KEY"],
        algorithms=["HS256"],
    )


def public_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "company": user.company,
        "role": user.role,
    }

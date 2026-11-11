from flask import jsonify, request
from werkzeug.security import check_password_hash

from app.api import api_bp
from app.api.deps import login_required
from app.api.errors import error
from app.extensions import db
from app.models import User
from app.services.audit import record_audit
from app.services.auth import create_jwt, public_user


@api_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    user = User.query.filter_by(email=email, active=True).first()
    if user is None or not check_password_hash(user.password_hash, password):
        record_audit(
            "login_failed",
            object_type="user",
            detail={"email": email},
            actor_label=email,
        )
        db.session.commit()
        return error("invalid_credentials", "邮箱或密码不正确", 401)

    token, expires_at = create_jwt(user)
    record_audit("login_success", object_type="user", object_id=user.id, actor=user)
    db.session.commit()

    return jsonify(
        {
            "data": {
                "token": token,
                "expires_at": expires_at.isoformat(),
                "user": public_user(user),
            }
        }
    )


@api_bp.get("/auth/me")
@login_required
def me():
    from flask import g

    return jsonify({"data": public_user(g.current_user)})

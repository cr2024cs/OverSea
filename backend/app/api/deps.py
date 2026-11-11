from functools import wraps

import jwt
from flask import g, request

from app.api.errors import error
from app.extensions import db
from app.models import User
from app.services.auth import decode_jwt


def _bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    return token or None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        if not token:
            return error("unauthorized", "请先登录", 401)
        try:
            payload = decode_jwt(token)
        except jwt.ExpiredSignatureError:
            return error("token_expired", "登录已过期，请重新登录", 401)
        except jwt.InvalidTokenError:
            return error("invalid_token", "登录凭证无效", 401)

        user = db.session.get(User, payload.get("sub"))
        if user is None or not user.active:
            return error("unauthorized", "用户不存在或已停用", 401)

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @login_required
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                return error("forbidden", "当前角色无权执行该操作", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator

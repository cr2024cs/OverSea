from flask import jsonify


def error(code, message, status=400, detail=None):
    payload = {"code": code, "message": message}
    if detail is not None:
        payload["detail"] = detail
    return jsonify(payload), status

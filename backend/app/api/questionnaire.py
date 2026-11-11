from flask import jsonify

from app.api import api_bp
from app.api.deps import login_required
from app.services.questionnaire import load_questionnaire


@api_bp.get("/questionnaire")
@login_required
def get_questionnaire():
    return jsonify({"data": load_questionnaire()})

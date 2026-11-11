from flask import jsonify

from app.api import api_bp
from app.models import ConfigItem


@api_bp.get("/config")
def get_config():
    rows = (
        ConfigItem.query.filter_by(enabled=True)
        .order_by(ConfigItem.type, ConfigItem.sort)
        .all()
    )
    grouped = {}
    for row in rows:
        grouped.setdefault(row.type, []).append(
            {
                "code": row.code,
                "name": row.name,
                "sort": row.sort,
                "extra": row.extra_json or {},
            }
        )
    return jsonify({"data": grouped})

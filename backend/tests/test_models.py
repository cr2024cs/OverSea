from sqlalchemy import inspect

from app.extensions import db

EXPECTED_TABLES = {
    "access_tokens",
    "archives",
    "audit_logs",
    "candidates",
    "client_quotes",
    "config_items",
    "contracts",
    "conversations",
    "documents",
    "facts",
    "findings",
    "knowledge_chunks",
    "messages",
    "milestones",
    "performance_events",
    "projects",
    "proposals",
    "providers",
    "query_letters",
    "quotes",
    "rfps",
    "task_templates",
    "tasks",
    "users",
}


def test_exactly_twentyfour_tables(app):
    with app.app_context():
        tables = set(inspect(db.engine).get_table_names())
    assert tables == EXPECTED_TABLES

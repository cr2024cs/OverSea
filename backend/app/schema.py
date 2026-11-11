from sqlalchemy import inspect, text

from app.extensions import db


def ensure_sqlite_columns():
    """SQLite 轻量迁移：为已存在的表补上模型中新增的列。

    只新增缺失列，不删除、不改类型；新增列一律允许 NULL，避免旧数据阻塞。
    """
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return []

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added = []

    for table in db.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_columns = {
            column["name"] for column in inspector.get_columns(table.name)
        }
        for column in table.columns:
            if column.name in existing_columns:
                continue

            type_sql = column.type.compile(dialect=engine.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {type_sql}'

            default = None
            if column.default is not None and not callable(column.default.arg):
                default = column.default.arg
            if isinstance(default, bool):
                ddl += f" DEFAULT {1 if default else 0}"
            elif isinstance(default, (int, float)):
                ddl += f" DEFAULT {default}"
            elif isinstance(default, str):
                escaped = default.replace("'", "''")
                ddl += f" DEFAULT '{escaped}'"

            with engine.begin() as connection:
                connection.execute(text(ddl))
            added.append(f"{table.name}.{column.name}")

    return added

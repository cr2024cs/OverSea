import sqlite3

from sqlalchemy import inspect

from app import create_app
from app.extensions import db


def test_old_sqlite_schema_is_auto_migrated(tmp_path):
    db_file = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_file)
    connection.execute(
        """
        CREATE TABLE users (
            id VARCHAR(32) PRIMARY KEY,
            email VARCHAR(200) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(120) NOT NULL,
            role VARCHAR(20) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "AUTO_CREATE_TABLES": True,
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "ARCHIVE_DIR": str(tmp_path / "archives"),
        }
    )
    with app.app_context():
        columns = {column["name"] for column in inspect(db.engine).get_columns("users")}
        assert "company" in columns
        assert "provider_id" in columns

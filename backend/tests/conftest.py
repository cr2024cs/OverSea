import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.ai.provider import AIProvider  # noqa: E402
from app.extensions import db  # noqa: E402
from tests.fake_ai import fake_remote  # noqa: E402


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    monkeypatch.setattr(AIProvider, "_remote", fake_remote)


@pytest.fixture
def app(tmp_path):
    db_file = tmp_path / "test.db"
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "AUTO_CREATE_TABLES": True,
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "ARCHIVE_DIR": str(tmp_path / "archives"),
            "AI_API_KEY": "test-key",
            "AI_STREAM_DELAY_MS": 0,
            "MAX_UPLOAD_BYTES": 200_000,
        }
    )
    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()

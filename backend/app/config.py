import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")

DATA_DIR = PROJECT_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
ARCHIVE_DIR = DATA_DIR / "archives"


def _sqlite_uri() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        return configured
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(DATA_DIR / 'oversea.db').as_posix()}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _sqlite_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_CREATE_TABLES = True

    AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
    AI_MODEL = os.getenv("AI_MODEL", "deepseek-v4.1-flash")
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "60"))
    AI_STREAM_DELAY_MS = int(os.getenv("AI_STREAM_DELAY_MS", "10"))
    MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))

    MANAGEMENT_FEE_RATE = float(os.getenv("MANAGEMENT_FEE_RATE", "0.175"))
    TOKEN_TTL_DAYS = int(os.getenv("TOKEN_TTL_DAYS", "14"))
    JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", "12"))

    UPLOAD_DIR = str(UPLOAD_DIR)
    ARCHIVE_DIR = str(ARCHIVE_DIR)

    JSON_AS_ASCII = False

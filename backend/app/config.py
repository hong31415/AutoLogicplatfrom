from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


def first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip().lstrip("\ufeff"), value.strip().strip('"').strip("'"))


for candidate in (BACKEND_ROOT / ".env", PROJECT_ROOT / ".env"):
    load_env(candidate)


@dataclass(frozen=True)
class Settings:
    host: str = os.environ.get("SUBDFA_BACKEND_HOST", "127.0.0.1")
    port: int = int(os.environ.get("SUBDFA_BACKEND_PORT", "8787"))
    api_prefix: str = os.environ.get("SUBDFA_API_PREFIX", "/api/v1")
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.environ.get(
            "SUBDFA_CORS_ORIGINS",
            "http://127.0.0.1:8790,http://localhost:8790,http://127.0.0.1:8765,http://localhost:8765",
        ).split(",")
        if item.strip()
    )
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    deepseek_model: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro").strip()
    deepseek_base_url: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
    embedding_api_key: str = first_env(
        "LOGICRAG_EMBEDDING_API_KEY",
        "DASHSCOPE_API_KEY",
        "OPENAI_API_KEY",
        "EMBEDDING_API_KEY",
    )
    embedding_model: str = os.environ.get("LOGICRAG_EMBEDDING_MODEL", "text-embedding-v4").strip()
    embedding_base_url: str = first_env(
        "LOGICRAG_EMBEDDING_BASE_URL",
        "DASHSCOPE_API_BASE",
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).rstrip("/")
    embedding_batch_size: int = int(os.environ.get("LOGICRAG_EMBEDDING_BATCH_SIZE", "10"))
    ifind_username: str = os.environ.get("IFIND_USERNAME", "").strip()
    ifind_password: str = os.environ.get("IFIND_PASSWORD", "").strip()
    ifind_enabled: bool = os.environ.get("SUBDFA_IFIND_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    tushare_token: str = os.environ.get("TUSHARE_TOKEN", "").strip()
    market_data_source: str = os.environ.get("SUBDFA_MARKET_DATA_SOURCE", "auto").strip().lower()
    market_data_cache_seconds: int = int(os.environ.get("SUBDFA_MARKET_DATA_CACHE_SECONDS", "300"))
    market_data_lookback_days: int = int(os.environ.get("SUBDFA_MARKET_DATA_LOOKBACK_DAYS", "45"))
    # The public checkout must start without a local MySQL installation. Private
    # deployments opt in through backend/.env or an environment variable.
    database_enabled: bool = os.environ.get("SUBDFA_DATABASE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    database_driver: str = os.environ.get("SUBDFA_DATABASE_DRIVER", "mysql").strip().lower()
    database_host: str = os.environ.get("SUBDFA_DATABASE_HOST", "127.0.0.1").strip()
    database_port: int = int(os.environ.get("SUBDFA_DATABASE_PORT", "3306"))
    database_name: str = os.environ.get("SUBDFA_DATABASE_NAME", "logicrag_subdfa").strip()
    database_user: str = os.environ.get("SUBDFA_DATABASE_USER", "root").strip()
    database_password: str = os.environ.get("SUBDFA_DATABASE_PASSWORD", "").strip()
    sqlite_path: str = os.environ.get(
        "SUBDFA_SQLITE_PATH",
        str(BACKEND_ROOT / "data" / "subdfa.sqlite3"),
    ).strip()
    request_timeout_seconds: int = int(os.environ.get("SUBDFA_REQUEST_TIMEOUT_SECONDS", "90"))
    demo_mode: bool = os.environ.get("SUBDFA_DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


settings = Settings()

if settings.embedding_api_key:
    os.environ.setdefault("LOGICRAG_EMBEDDING_API_KEY", settings.embedding_api_key)
if settings.embedding_model:
    os.environ.setdefault("LOGICRAG_EMBEDDING_MODEL", settings.embedding_model)
if settings.embedding_base_url:
    os.environ.setdefault("LOGICRAG_EMBEDDING_BASE_URL", settings.embedding_base_url)
os.environ.setdefault("LOGICRAG_EMBEDDING_BATCH_SIZE", str(settings.embedding_batch_size))
if settings.ifind_username:
    os.environ.setdefault("IFIND_USERNAME", settings.ifind_username)
if settings.ifind_password:
    os.environ.setdefault("IFIND_PASSWORD", settings.ifind_password)

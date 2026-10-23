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


@dataclass
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
    deepseek_model: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
    deepseek_base_url: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
    generation_provider: str = os.environ.get("SUBDFA_GENERATION_PROVIDER", "deepseek").strip().lower()
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "").strip()
    openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini").strip()
    openai_base_url: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    kimi_api_key: str = os.environ.get("KIMI_API_KEY", "").strip()
    kimi_model: str = os.environ.get("KIMI_MODEL", "moonshot-v1-32k").strip()
    kimi_base_url: str = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1").strip().rstrip("/")
    doubao_api_key: str = os.environ.get("DOUBAO_API_KEY", "").strip()
    doubao_model: str = os.environ.get("DOUBAO_MODEL", "doubao-seed-1-6-250615").strip()
    doubao_base_url: str = os.environ.get("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").strip().rstrip("/")
    custom_generation_api_key: str = os.environ.get("CUSTOM_GENERATION_API_KEY", "").strip()
    custom_generation_model: str = os.environ.get("CUSTOM_GENERATION_MODEL", "custom-model").strip()
    custom_generation_base_url: str = os.environ.get("CUSTOM_GENERATION_BASE_URL", "https://example.com/v1").strip().rstrip("/")
    embedding_provider: str = os.environ.get("LOGICRAG_EMBEDDING_PROVIDER", "dashscope").strip().lower()
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
    dashscope_embedding_api_key: str = first_env("DASHSCOPE_EMBEDDING_API_KEY", "DASHSCOPE_API_KEY")
    dashscope_embedding_model: str = os.environ.get("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4").strip()
    dashscope_embedding_base_url: str = os.environ.get(
        "DASHSCOPE_EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).strip().rstrip("/")
    openai_embedding_api_key: str = os.environ.get("OPENAI_EMBEDDING_API_KEY", "").strip()
    openai_embedding_model: str = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large").strip()
    openai_embedding_base_url: str = os.environ.get(
        "OPENAI_EMBEDDING_BASE_URL", "https://api.openai.com/v1"
    ).strip().rstrip("/")
    doubao_embedding_api_key: str = os.environ.get("DOUBAO_EMBEDDING_API_KEY", "").strip()
    doubao_embedding_model: str = os.environ.get(
        "DOUBAO_EMBEDDING_MODEL", "doubao-embedding-large-text-250515"
    ).strip()
    doubao_embedding_base_url: str = os.environ.get(
        "DOUBAO_EMBEDDING_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
    ).strip().rstrip("/")
    zhipu_embedding_api_key: str = os.environ.get("ZHIPU_EMBEDDING_API_KEY", "").strip()
    zhipu_embedding_model: str = os.environ.get("ZHIPU_EMBEDDING_MODEL", "embedding-3").strip()
    zhipu_embedding_base_url: str = os.environ.get(
        "ZHIPU_EMBEDDING_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
    ).strip().rstrip("/")
    custom_embedding_api_key: str = os.environ.get("CUSTOM_EMBEDDING_API_KEY", "").strip()
    custom_embedding_model: str = os.environ.get("CUSTOM_EMBEDDING_MODEL", "embedding-model").strip()
    custom_embedding_base_url: str = os.environ.get(
        "CUSTOM_EMBEDDING_BASE_URL", "https://example.com/v1"
    ).strip().rstrip("/")
    embedding_batch_size: int = int(os.environ.get("LOGICRAG_EMBEDDING_BATCH_SIZE", "10"))
    ifind_username: str = os.environ.get("IFIND_USERNAME", "").strip()
    ifind_password: str = os.environ.get("IFIND_PASSWORD", "").strip()
    ifind_enabled: bool = os.environ.get("SUBDFA_IFIND_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    tushare_token: str = os.environ.get("TUSHARE_TOKEN", "").strip()
    market_data_source: str = os.environ.get("SUBDFA_MARKET_DATA_SOURCE", "auto").strip().lower()
    akshare_enabled: bool = os.environ.get("SUBDFA_AKSHARE_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
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
    # Required when a non-loopback deployment exposes the API settings editor.
    # Local desktop deployments may edit configuration without a token.
    config_admin_token: str = os.environ.get("SUBDFA_CONFIG_ADMIN_TOKEN", "").strip()

    def active_generation_profile(self) -> dict[str, str]:
        profiles = {
            "deepseek": (self.deepseek_api_key, self.deepseek_model, self.deepseek_base_url),
            "openai": (self.openai_api_key, self.openai_model, self.openai_base_url),
            "kimi": (self.kimi_api_key, self.kimi_model, self.kimi_base_url),
            "doubao": (self.doubao_api_key, self.doubao_model, self.doubao_base_url),
            "custom": (
                self.custom_generation_api_key,
                self.custom_generation_model,
                self.custom_generation_base_url,
            ),
        }
        provider = self.generation_provider if self.generation_provider in profiles else "deepseek"
        api_key, model, base_url = profiles[provider]
        return {"provider": provider, "api_key": api_key, "model": model, "base_url": base_url}

    def active_embedding_profile(self) -> dict[str, str]:
        dashscope_key = self.dashscope_embedding_api_key or (
            self.embedding_api_key if self.embedding_provider in {"", "dashscope"} else ""
        )
        profiles = {
            "dashscope": (
                dashscope_key,
                self.dashscope_embedding_model or self.embedding_model,
                self.dashscope_embedding_base_url or self.embedding_base_url,
            ),
            "openai": (
                self.openai_embedding_api_key,
                self.openai_embedding_model,
                self.openai_embedding_base_url,
            ),
            "doubao": (
                self.doubao_embedding_api_key,
                self.doubao_embedding_model,
                self.doubao_embedding_base_url,
            ),
            "zhipu": (
                self.zhipu_embedding_api_key,
                self.zhipu_embedding_model,
                self.zhipu_embedding_base_url,
            ),
            "custom": (
                self.custom_embedding_api_key,
                self.custom_embedding_model,
                self.custom_embedding_base_url,
            ),
        }
        provider = self.embedding_provider if self.embedding_provider in profiles else "dashscope"
        api_key, model, base_url = profiles[provider]
        return {"provider": provider, "api_key": api_key, "model": model, "base_url": base_url}


settings = Settings()

active_embedding = settings.active_embedding_profile()
settings.embedding_api_key = active_embedding["api_key"]
settings.embedding_model = active_embedding["model"]
settings.embedding_base_url = active_embedding["base_url"]
if settings.embedding_api_key:
    os.environ["LOGICRAG_EMBEDDING_API_KEY"] = settings.embedding_api_key
else:
    os.environ.pop("LOGICRAG_EMBEDDING_API_KEY", None)
if settings.embedding_model:
    os.environ["LOGICRAG_EMBEDDING_MODEL"] = settings.embedding_model
if settings.embedding_base_url:
    os.environ["LOGICRAG_EMBEDDING_BASE_URL"] = settings.embedding_base_url
os.environ.setdefault("LOGICRAG_EMBEDDING_BATCH_SIZE", str(settings.embedding_batch_size))
if settings.ifind_username:
    os.environ.setdefault("IFIND_USERNAME", settings.ifind_username)
if settings.ifind_password:
    os.environ.setdefault("IFIND_PASSWORD", settings.ifind_password)

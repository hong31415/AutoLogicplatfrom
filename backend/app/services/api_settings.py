from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.config import BACKEND_ROOT, Settings


ENV_PATH = BACKEND_ROOT / ".env"

GENERATION_PROVIDERS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "label": "DeepSeek",
        "env": ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"),
        "attrs": ("deepseek_api_key", "deepseek_model", "deepseek_base_url"),
    },
    "openai": {
        "label": "GPT / OpenAI",
        "env": ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"),
        "attrs": ("openai_api_key", "openai_model", "openai_base_url"),
    },
    "kimi": {
        "label": "Kimi / Moonshot",
        "env": ("KIMI_API_KEY", "KIMI_MODEL", "KIMI_BASE_URL"),
        "attrs": ("kimi_api_key", "kimi_model", "kimi_base_url"),
    },
    "doubao": {
        "label": "豆包 / Volcengine",
        "env": ("DOUBAO_API_KEY", "DOUBAO_MODEL", "DOUBAO_BASE_URL"),
        "attrs": ("doubao_api_key", "doubao_model", "doubao_base_url"),
    },
    "custom": {
        "label": "自定义兼容接口",
        "env": ("CUSTOM_GENERATION_API_KEY", "CUSTOM_GENERATION_MODEL", "CUSTOM_GENERATION_BASE_URL"),
        "attrs": (
            "custom_generation_api_key",
            "custom_generation_model",
            "custom_generation_base_url",
        ),
    },
}

EMBEDDING_PROVIDERS: dict[str, dict[str, Any]] = {
    "dashscope": {
        "label": "阿里云百炼 / DashScope",
        "env": (
            "DASHSCOPE_EMBEDDING_API_KEY",
            "DASHSCOPE_EMBEDDING_MODEL",
            "DASHSCOPE_EMBEDDING_BASE_URL",
        ),
        "attrs": (
            "dashscope_embedding_api_key",
            "dashscope_embedding_model",
            "dashscope_embedding_base_url",
        ),
    },
    "openai": {
        "label": "OpenAI Embedding",
        "env": ("OPENAI_EMBEDDING_API_KEY", "OPENAI_EMBEDDING_MODEL", "OPENAI_EMBEDDING_BASE_URL"),
        "attrs": (
            "openai_embedding_api_key",
            "openai_embedding_model",
            "openai_embedding_base_url",
        ),
    },
    "doubao": {
        "label": "豆包 Embedding",
        "env": ("DOUBAO_EMBEDDING_API_KEY", "DOUBAO_EMBEDDING_MODEL", "DOUBAO_EMBEDDING_BASE_URL"),
        "attrs": (
            "doubao_embedding_api_key",
            "doubao_embedding_model",
            "doubao_embedding_base_url",
        ),
    },
    "zhipu": {
        "label": "智谱 Embedding",
        "env": ("ZHIPU_EMBEDDING_API_KEY", "ZHIPU_EMBEDDING_MODEL", "ZHIPU_EMBEDDING_BASE_URL"),
        "attrs": (
            "zhipu_embedding_api_key",
            "zhipu_embedding_model",
            "zhipu_embedding_base_url",
        ),
    },
    "custom": {
        "label": "自定义兼容接口",
        "env": ("CUSTOM_EMBEDDING_API_KEY", "CUSTOM_EMBEDDING_MODEL", "CUSTOM_EMBEDDING_BASE_URL"),
        "attrs": (
            "custom_embedding_api_key",
            "custom_embedding_model",
            "custom_embedding_base_url",
        ),
    },
}

MANAGED_KEYS = (
    "SUBDFA_GENERATION_PROVIDER",
    *(key for item in GENERATION_PROVIDERS.values() for key in item["env"]),
    "LOGICRAG_EMBEDDING_PROVIDER",
    *(key for item in EMBEDDING_PROVIDERS.values() for key in item["env"]),
    "LOGICRAG_EMBEDDING_API_KEY",
    "LOGICRAG_EMBEDDING_MODEL",
    "LOGICRAG_EMBEDDING_BASE_URL",
    "SUBDFA_MARKET_DATA_SOURCE",
    "SUBDFA_AKSHARE_ENABLED",
    "TUSHARE_TOKEN",
    "SUBDFA_IFIND_ENABLED",
    "IFIND_USERNAME",
    "IFIND_PASSWORD",
)


def masked_secret(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    suffix = text[-4:] if len(text) >= 4 else text
    return f"••••{suffix}"


def _profile_public(settings: Settings, definition: dict[str, Any]) -> dict[str, Any]:
    api_attr, model_attr, base_attr = definition["attrs"]
    api_key = str(getattr(settings, api_attr, "") or "")
    model = str(getattr(settings, model_attr, "") or "")
    base_url = str(getattr(settings, base_attr, "") or "")
    if api_attr == "dashscope_embedding_api_key" and not api_key:
        api_key = settings.embedding_api_key
        model = settings.embedding_model or model
        base_url = settings.embedding_base_url or base_url
    return {
        "label": definition["label"],
        "configured": bool(api_key),
        "masked": masked_secret(api_key),
        "model": model,
        "base_url": base_url,
    }


def public_api_settings(settings: Settings) -> dict[str, Any]:
    generation_profiles = {
        provider: _profile_public(settings, definition)
        for provider, definition in GENERATION_PROVIDERS.items()
    }
    embedding_profiles = {
        provider: _profile_public(settings, definition)
        for provider, definition in EMBEDDING_PROVIDERS.items()
    }
    generation_active = (
        settings.generation_provider if settings.generation_provider in GENERATION_PROVIDERS else "deepseek"
    )
    embedding_active = (
        settings.embedding_provider if settings.embedding_provider in EMBEDDING_PROVIDERS else "dashscope"
    )
    active_generation = generation_profiles[generation_active]
    active_embedding = embedding_profiles[embedding_active]
    akshare_installed = importlib.util.find_spec("akshare") is not None
    tushare_installed = importlib.util.find_spec("tushare") is not None
    evidence = {
        "active_source": settings.market_data_source,
        "akshare": {
            "enabled": settings.akshare_enabled,
            "installed": akshare_installed,
            "configured": settings.akshare_enabled and akshare_installed,
            "requires_credentials": False,
        },
        "tushare": {
            "installed": tushare_installed,
            "configured": bool(settings.tushare_token),
            "masked": masked_secret(settings.tushare_token),
        },
        "ifind": {
            "enabled": settings.ifind_enabled,
            "configured": bool(settings.ifind_username and settings.ifind_password),
            "username_masked": masked_secret(settings.ifind_username),
            "password_masked": masked_secret(settings.ifind_password),
        },
    }
    return {
        "requires_admin_token": bool(settings.config_admin_token),
        "remote_editing_enabled": bool(settings.config_admin_token),
        "generation": {
            "active_provider": generation_active,
            "configured": active_generation["configured"],
            "provider_label": active_generation["label"],
            "model": active_generation["model"],
            "providers": generation_profiles,
        },
        "embedding": {
            "active_provider": embedding_active,
            "configured": active_embedding["configured"],
            "provider_label": active_embedding["label"],
            "masked": active_embedding["masked"],
            "model": active_embedding["model"],
            "base_url": active_embedding["base_url"],
            "providers": embedding_profiles,
        },
        "evidence": evidence,
        "deepseek": generation_profiles["deepseek"],
        "tushare": evidence["tushare"],
        "ifind": evidence["ifind"],
    }


def _clean_text(value: Any, *, name: str, maximum: int = 500) -> str:
    text = str(value or "").strip()
    if "\n" in text or "\r" in text or "\x00" in text:
        raise ValueError(f"{name} contains an invalid line break")
    if len(text) > maximum:
        raise ValueError(f"{name} is too long")
    return text


def _validated_url(value: Any, *, name: str) -> str:
    text = _clean_text(value, name=name, maximum=500).rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be a valid HTTP or HTTPS URL")
    return text


def _secret_update(section: dict[str, Any], field: str, clear_field: str, current: str, name: str) -> str:
    if bool(section.get(clear_field)):
        return ""
    supplied = _clean_text(section.get(field), name=name, maximum=2000)
    return supplied or current


def _normalize_profiles(
    *,
    payload_section: dict[str, Any],
    settings: Settings,
    definitions: dict[str, dict[str, Any]],
    kind: str,
) -> dict[str, str]:
    updates: dict[str, str] = {}
    supplied_profiles = payload_section.get("providers")
    supplied_profiles = supplied_profiles if isinstance(supplied_profiles, dict) else {}
    for provider, definition in definitions.items():
        section = supplied_profiles.get(provider)
        section = section if isinstance(section, dict) else {}
        key_env, model_env, base_env = definition["env"]
        key_attr, model_attr, base_attr = definition["attrs"]
        current_key = str(getattr(settings, key_attr, "") or "")
        if kind == "embedding" and provider == "dashscope" and not current_key:
            current_key = settings.embedding_api_key
        current_model = str(getattr(settings, model_attr, "") or "")
        current_base = str(getattr(settings, base_attr, "") or "")
        label = str(definition["label"])
        updates[key_env] = _secret_update(
            section, "api_key", "clear_api_key", current_key, f"{label} API Key"
        )
        updates[model_env] = _clean_text(
            section.get("model") or current_model, name=f"{label} model", maximum=160
        )
        updates[base_env] = _validated_url(
            section.get("base_url") or current_base, name=f"{label} base URL"
        )
    return updates


def normalize_api_settings_payload(payload: dict[str, Any], settings: Settings) -> dict[str, str]:
    generation = payload.get("generation") if isinstance(payload.get("generation"), dict) else {}
    legacy_deepseek = payload.get("deepseek") if isinstance(payload.get("deepseek"), dict) else {}
    if not generation and legacy_deepseek:
        generation = {"active_provider": "deepseek", "providers": {"deepseek": legacy_deepseek}}

    embedding = payload.get("embedding") if isinstance(payload.get("embedding"), dict) else {}
    if embedding and not isinstance(embedding.get("providers"), dict):
        embedding = {
            "active_provider": settings.embedding_provider or "dashscope",
            "providers": {settings.embedding_provider or "dashscope": embedding},
        }

    generation_provider = _clean_text(
        generation.get("active_provider") or settings.generation_provider,
        name="generation provider",
        maximum=40,
    ).lower()
    if generation_provider not in GENERATION_PROVIDERS:
        raise ValueError("Unsupported generation provider")
    embedding_provider = _clean_text(
        embedding.get("active_provider") or settings.embedding_provider,
        name="embedding provider",
        maximum=40,
    ).lower()
    if embedding_provider not in EMBEDDING_PROVIDERS:
        raise ValueError("Unsupported embedding provider")

    updates = {
        "SUBDFA_GENERATION_PROVIDER": generation_provider,
        **_normalize_profiles(
            payload_section=generation,
            settings=settings,
            definitions=GENERATION_PROVIDERS,
            kind="generation",
        ),
        "LOGICRAG_EMBEDDING_PROVIDER": embedding_provider,
        **_normalize_profiles(
            payload_section=embedding,
            settings=settings,
            definitions=EMBEDDING_PROVIDERS,
            kind="embedding",
        ),
    }

    embedding_definition = EMBEDDING_PROVIDERS[embedding_provider]
    selected_embedding_env = embedding_definition["env"]
    updates["LOGICRAG_EMBEDDING_API_KEY"] = updates[selected_embedding_env[0]]
    updates["LOGICRAG_EMBEDDING_MODEL"] = updates[selected_embedding_env[1]]
    updates["LOGICRAG_EMBEDDING_BASE_URL"] = updates[selected_embedding_env[2]]

    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    tushare = evidence.get("tushare") if isinstance(evidence.get("tushare"), dict) else {}
    if not tushare:
        tushare = payload.get("tushare") if isinstance(payload.get("tushare"), dict) else {}
    ifind = evidence.get("ifind") if isinstance(evidence.get("ifind"), dict) else {}
    if not ifind:
        ifind = payload.get("ifind") if isinstance(payload.get("ifind"), dict) else {}
    akshare = evidence.get("akshare") if isinstance(evidence.get("akshare"), dict) else {}
    active_source = _clean_text(
        evidence.get("active_source") or settings.market_data_source,
        name="market data source",
        maximum=40,
    ).lower()
    if active_source not in {"auto", "akshare", "tushare", "ifind", "demo", "none"}:
        raise ValueError("Unsupported market data source")
    akshare_enabled = settings.akshare_enabled if "enabled" not in akshare else bool(akshare.get("enabled"))
    ifind_enabled = settings.ifind_enabled if "enabled" not in ifind else bool(ifind.get("enabled"))
    updates.update(
        {
            "SUBDFA_MARKET_DATA_SOURCE": active_source,
            "SUBDFA_AKSHARE_ENABLED": "true" if akshare_enabled else "false",
            "TUSHARE_TOKEN": _secret_update(
                tushare, "token", "clear_token", settings.tushare_token, "Tushare token"
            ),
            "SUBDFA_IFIND_ENABLED": "true" if ifind_enabled else "false",
            "IFIND_USERNAME": (
                ""
                if bool(ifind.get("clear_credentials"))
                else _clean_text(ifind.get("username"), name="iFinD username", maximum=200)
                or settings.ifind_username
            ),
            "IFIND_PASSWORD": (
                ""
                if bool(ifind.get("clear_credentials"))
                else _secret_update(
                    ifind, "password", "clear_password", settings.ifind_password, "iFinD password"
                )
            ),
        }
    )
    return updates


def write_env_updates(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    replaced: set[str] = set()
    output: list[str] = []
    key_pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for line in lines:
        match = key_pattern.match(line)
        key = match.group(1) if match else ""
        if key in updates:
            output.append(f"{key}={updates[key]}")
            replaced.add(key)
        else:
            output.append(line)
    missing = [key for key in MANAGED_KEYS if key in updates and key not in replaced]
    if missing and output and output[-1].strip():
        output.append("")
    if missing:
        output.append("# API credentials managed by the AutoLogic Studio settings screen.")
        output.extend(f"{key}={updates[key]}" for key in missing)
    temporary = path.with_suffix(".env.tmp")
    temporary.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def apply_api_settings(settings: Settings, updates: dict[str, str]) -> None:
    for key, value in updates.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    settings.generation_provider = updates["SUBDFA_GENERATION_PROVIDER"]
    settings.embedding_provider = updates["LOGICRAG_EMBEDDING_PROVIDER"]
    for definitions in (GENERATION_PROVIDERS, EMBEDDING_PROVIDERS):
        for definition in definitions.values():
            for env_key, attr in zip(definition["env"], definition["attrs"]):
                setattr(settings, attr, updates[env_key])

    settings.embedding_api_key = updates["LOGICRAG_EMBEDDING_API_KEY"]
    settings.embedding_model = updates["LOGICRAG_EMBEDDING_MODEL"]
    settings.embedding_base_url = updates["LOGICRAG_EMBEDDING_BASE_URL"]
    settings.market_data_source = updates["SUBDFA_MARKET_DATA_SOURCE"]
    settings.akshare_enabled = updates["SUBDFA_AKSHARE_ENABLED"] == "true"
    settings.tushare_token = updates["TUSHARE_TOKEN"]
    settings.ifind_enabled = updates["SUBDFA_IFIND_ENABLED"] == "true"
    settings.ifind_username = updates["IFIND_USERNAME"]
    settings.ifind_password = updates["IFIND_PASSWORD"]


def save_api_settings(payload: dict[str, Any], settings: Settings, path: Path = ENV_PATH) -> dict[str, Any]:
    updates = normalize_api_settings_payload(payload, settings)
    write_env_updates(path, updates)
    apply_api_settings(settings, updates)
    return public_api_settings(settings)

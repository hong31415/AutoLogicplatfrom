from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.services.api_settings import (
    normalize_api_settings_payload,
    public_api_settings,
    save_api_settings,
)


class ApiSettingsTest(unittest.TestCase):
    def make_settings(self) -> Settings:
        return Settings(
            deepseek_api_key="old-deepseek-1234",
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com",
            embedding_api_key="old-embedding-5678",
            embedding_model="text-embedding-v4",
            embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            tushare_token="old-tushare-9012",
            ifind_enabled=False,
            ifind_username="",
            ifind_password="",
        )

    def test_public_settings_are_masked(self) -> None:
        payload = public_api_settings(self.make_settings())
        serialized = str(payload)
        self.assertTrue(payload["deepseek"]["configured"])
        self.assertEqual(payload["deepseek"]["masked"], "••••1234")
        self.assertNotIn("old-deepseek", serialized)
        self.assertNotIn("old-embedding", serialized)
        self.assertNotIn("old-tushare", serialized)

    def test_blank_secret_keeps_existing_value_and_clear_removes_it(self) -> None:
        settings = self.make_settings()
        updates = normalize_api_settings_payload(
            {
                "deepseek": {"api_key": "", "model": "deepseek-reasoner", "base_url": "https://api.deepseek.com"},
                "embedding": {"api_key": "", "model": "text-embedding-v4", "base_url": "https://example.com/v1"},
                "tushare": {"clear_token": True},
                "ifind": {"enabled": False},
            },
            settings,
        )
        self.assertEqual(updates["DEEPSEEK_API_KEY"], "old-deepseek-1234")
        self.assertEqual(updates["DEEPSEEK_MODEL"], "deepseek-reasoner")
        self.assertEqual(updates["TUSHARE_TOKEN"], "")

    def test_save_persists_and_applies_without_returning_plaintext(self) -> None:
        settings = self.make_settings()
        previous = {name: os.environ.get(name) for name in (
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_MODEL",
            "DEEPSEEK_BASE_URL",
            "LOGICRAG_EMBEDDING_API_KEY",
            "LOGICRAG_EMBEDDING_MODEL",
            "LOGICRAG_EMBEDDING_BASE_URL",
            "TUSHARE_TOKEN",
            "SUBDFA_IFIND_ENABLED",
            "IFIND_USERNAME",
            "IFIND_PASSWORD",
        )}
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / ".env"
                path.write_text("# keep this comment\nDEEPSEEK_MODEL=old-model\n", encoding="utf-8")
                result = save_api_settings(
                    {
                        "deepseek": {"api_key": "new-secret-ABCD", "model": "deepseek-chat", "base_url": "https://api.deepseek.com"},
                        "embedding": {"api_key": "embed-secret-EFGH", "model": "embed-model", "base_url": "https://example.com/v1"},
                        "tushare": {"token": "tushare-IJKL"},
                        "ifind": {"enabled": True, "username": "demo-user", "password": "ifind-MNOP"},
                    },
                    settings,
                    path,
                )
                saved = path.read_text(encoding="utf-8")
                self.assertIn("# keep this comment", saved)
                self.assertIn("DEEPSEEK_API_KEY=new-secret-ABCD", saved)
                self.assertEqual(settings.deepseek_api_key, "new-secret-ABCD")
                self.assertEqual(result["deepseek"]["masked"], "••••ABCD")
                self.assertNotIn("new-secret-ABCD", str(result))
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_rejects_invalid_url_and_line_breaks(self) -> None:
        settings = self.make_settings()
        with self.assertRaises(ValueError):
            normalize_api_settings_payload(
                {"deepseek": {"base_url": "not-a-url"}},
                settings,
            )
        with self.assertRaises(ValueError):
            normalize_api_settings_payload(
                {"deepseek": {"api_key": "secret\nINJECTED=true"}},
                settings,
            )

    def test_multiple_generation_and_embedding_profiles_can_be_saved_and_switched(self) -> None:
        settings = self.make_settings()
        updates = normalize_api_settings_payload(
            {
                "generation": {
                    "active_provider": "openai",
                    "providers": {
                        "deepseek": {
                            "api_key": "",
                            "model": "deepseek-chat",
                            "base_url": "https://api.deepseek.com",
                        },
                        "openai": {
                            "api_key": "openai-secret-2468",
                            "model": "gpt-4.1-mini",
                            "base_url": "https://api.openai.com/v1",
                        },
                        "kimi": {
                            "api_key": "kimi-secret-1357",
                            "model": "moonshot-v1-32k",
                            "base_url": "https://api.moonshot.cn/v1",
                        },
                    },
                },
                "embedding": {
                    "active_provider": "zhipu",
                    "providers": {
                        "dashscope": {
                            "api_key": "",
                            "model": "text-embedding-v4",
                            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                        },
                        "zhipu": {
                            "api_key": "zhipu-secret-9753",
                            "model": "embedding-3",
                            "base_url": "https://open.bigmodel.cn/api/paas/v4",
                        },
                    },
                },
                "evidence": {
                    "active_source": "akshare",
                    "akshare": {"enabled": True},
                },
            },
            settings,
        )
        self.assertEqual(updates["SUBDFA_GENERATION_PROVIDER"], "openai")
        self.assertEqual(updates["OPENAI_API_KEY"], "openai-secret-2468")
        self.assertEqual(updates["KIMI_API_KEY"], "kimi-secret-1357")
        self.assertEqual(updates["LOGICRAG_EMBEDDING_PROVIDER"], "zhipu")
        self.assertEqual(updates["LOGICRAG_EMBEDDING_API_KEY"], "zhipu-secret-9753")
        self.assertEqual(updates["SUBDFA_MARKET_DATA_SOURCE"], "akshare")
        self.assertEqual(updates["SUBDFA_AKSHARE_ENABLED"], "true")


if __name__ == "__main__":
    unittest.main()

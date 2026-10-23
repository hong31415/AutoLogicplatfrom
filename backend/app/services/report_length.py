from __future__ import annotations

from typing import Any


DEFAULT_REPORT_LENGTH = "standard"

REPORT_LENGTH_PRESETS: dict[str, dict[str, Any]] = {
    "concise": {
        "label_zh": "精简",
        "label_en": "Concise",
        "zh_range": (800, 1200),
        "en_range": (500, 800),
    },
    "standard": {
        "label_zh": "标准",
        "label_en": "Standard",
        "zh_range": (1800, 2500),
        "en_range": (1000, 1600),
    },
    "detailed": {
        "label_zh": "详细",
        "label_en": "Detailed",
        "zh_range": (3500, 5000),
        "en_range": (2200, 3200),
    },
}


def normalize_report_length(value: Any) -> str:
    key = str(value or DEFAULT_REPORT_LENGTH).strip().lower()
    return key if key in REPORT_LENGTH_PRESETS else DEFAULT_REPORT_LENGTH


def report_length_config(value: Any, language: str = "zh") -> dict[str, Any]:
    key = normalize_report_length(value)
    english = str(language).lower().startswith("en")
    preset = REPORT_LENGTH_PRESETS[key]
    minimum, maximum = preset["en_range" if english else "zh_range"]
    return {
        "key": key,
        "label": preset["label_en" if english else "label_zh"],
        "min": minimum,
        "max": maximum,
        "unit": "words" if english else "Chinese characters",
    }

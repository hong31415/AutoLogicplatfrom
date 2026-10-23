from __future__ import annotations

import json
import unittest

from app.services.deepseek import build_prompt
from app.services.pipeline import options_from_payload
from app.services.report_length import report_length_config


class ReportLengthTests(unittest.TestCase):
    def test_default_is_standard(self) -> None:
        options = options_from_payload({})
        self.assertEqual(options.report_length, "standard")
        self.assertEqual(report_length_config(options.report_length)["min"], 1800)
        self.assertEqual(report_length_config(options.report_length)["max"], 2500)

    def test_allowed_presets_are_preserved(self) -> None:
        self.assertEqual(options_from_payload({"report_length": "concise"}).report_length, "concise")
        self.assertEqual(options_from_payload({"report_length": "detailed"}).report_length, "detailed")

    def test_invalid_preset_falls_back_to_standard(self) -> None:
        options = options_from_payload({"report_length": "999999"})
        self.assertEqual(options.report_length, "standard")

    def test_prompt_does_not_trust_client_supplied_numeric_range(self) -> None:
        section = [{"node_id": "S1", "label": "Overview", "order": 1, "content": "draft"}]
        payload = json.loads(build_prompt(
            "weekly report",
            "2025-06-08",
            section,
            {},
            "zh",
            {"key": "concise", "min": 1, "max": 999999, "unit": "tokens"},
        ))
        self.assertEqual(payload["length_control"]["min"], 800)
        self.assertEqual(payload["length_control"]["max"], 1200)

    def test_prompt_contains_total_and_dynamic_per_section_targets(self) -> None:
        sections = [
            {"node_id": f"S{index}", "label": f"Section {index}", "order": index, "content": "draft"}
            for index in range(1, 6)
        ]
        payload = json.loads(build_prompt(
            "weekly report",
            "2025-06-08",
            sections,
            {},
            "zh",
            "standard",
        ))
        length = payload["length_control"]
        self.assertEqual(length["key"], "standard")
        self.assertEqual((length["min"], length["max"]), (1800, 2500))
        self.assertEqual((length["average_per_section_min"], length["average_per_section_max"]), (360, 500))
        self.assertTrue(any("1800-2500 Chinese characters" in item for item in payload["requirements"]))

    def test_english_uses_word_ranges(self) -> None:
        config = report_length_config("concise", "en")
        self.assertEqual(config["unit"], "words")
        self.assertEqual((config["min"], config["max"]), (500, 800))


if __name__ == "__main__":
    unittest.main()

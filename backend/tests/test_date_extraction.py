from __future__ import annotations

import unittest
from datetime import date

from app.services.pipeline import extract_date


class ExtractDateTests(unittest.TestCase):
    def test_three_homepage_examples_use_historical_cutoffs(self) -> None:
        examples = {
            "2025-06-02 to 2025-06-08": "2025-06-08",
            "2025-06-02 至 2025-06-08": "2025-06-08",
            "January 2026": "2026-01-31",
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(extract_date(f"Time range: {text}", date(2026, 8, 25)), expected)

    def test_all_time_range_presets_are_supported(self) -> None:
        examples = {
            "2025/11/24-2025/11/30": "2025-11-30",
            "Dec 1–7, 2025": "2025-12-07",
            "Q1 2026": "2026-03-31",
            "2026 Q1": "2026-03-31",
            "As of 2026-03-31": "2026-03-31",
            "2026年1月": "2026-01-31",
            "2026年第一季度": "2026-03-31",
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(extract_date(text, date(2026, 8, 25)), expected)


if __name__ == "__main__":
    unittest.main()

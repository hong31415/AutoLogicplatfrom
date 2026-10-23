from __future__ import annotations

import unittest
from datetime import date

from app.services.market_data import _record_partitions_from_frame, _records_from_frame


class FakeFrame:
    empty = False

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def to_dict(self, orient: str = "records") -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError(orient)
        return self.rows


class MarketDataRangeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = FakeFrame([
            {"date": "2025-05-29", "close": 0.8},
            {"date": "2025-05-30", "close": 0.9},
            {"date": "2025-06-03", "close": 1},
            {"date": "2025-06-04", "close": 2},
            {"date": "2025-06-05", "close": 3},
            {"date": "2025-06-06", "close": 4},
            {"date": "2025-06-09", "close": 5},
        ])

    def test_explicit_range_keeps_every_available_record(self) -> None:
        records = _records_from_frame(
            self.frame,
            target=date(2025, 6, 8),
            endpoint="futures_zh_daily_sina",
            start=date(2025, 6, 2),
        )
        self.assertEqual([item["date"] for item in records], [
            "2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06",
        ])

    def test_cutoff_only_retains_legacy_last_three_records(self) -> None:
        records = _records_from_frame(
            self.frame,
            target=date(2025, 6, 8),
            endpoint="futures_zh_daily_sina",
        )
        self.assertEqual([item["date"] for item in records], [
            "2025-06-04", "2025-06-05", "2025-06-06",
        ])

    def test_pre_period_records_are_kept_as_lower_weight_baseline(self) -> None:
        records, context = _record_partitions_from_frame(
            self.frame,
            target=date(2025, 6, 8),
            endpoint="futures_zh_daily_sina",
            start=date(2025, 6, 2),
        )
        self.assertEqual(len(records), 4)
        self.assertEqual([item["record"]["date"] for item in context], ["2025-05-29", "2025-05-30"])
        self.assertTrue(all(0.2 <= item["weight"] < 1.0 for item in context))
        self.assertGreater(context[-1]["weight"], context[0]["weight"])


if __name__ == "__main__":
    unittest.main()

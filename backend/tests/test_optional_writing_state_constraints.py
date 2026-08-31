from __future__ import annotations

import unittest

from logicrag_core.query_processing import apply_query_label_boost
from app.services.pipeline import select_domain


class OptionalWritingStateConstraintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.states = [
            {"state_id": "S01", "node_id": "S01", "label": "Market Review", "similarity": 0.31},
            {"state_id": "S02", "node_id": "S02", "label": "Risk Factors", "similarity": 0.22},
        ]

    def test_high_level_query_does_not_force_a_named_writing_state(self) -> None:
        ranked = apply_query_label_boost(
            "Explain the week's market changes and implications for positioning.",
            self.states,
        )
        by_id = {item["state_id"]: item for item in ranked}
        self.assertEqual(by_id["S02"]["similarity"], 0.22)
        self.assertNotIn("match_reason", by_id["S02"])

    def test_optional_constraint_boosts_the_named_writing_state(self) -> None:
        ranked = apply_query_label_boost(
            "Optional writing-state constraints: Risk Factors",
            self.states,
        )
        by_id = {item["state_id"]: item for item in ranked}
        self.assertEqual(by_id["S02"]["similarity"], 0.92)
        self.assertEqual(by_id["S02"]["match_reason"], "explicit-label")

    def test_precious_metals_query_with_industry_tracking_is_not_classified_as_etf(self) -> None:
        query = (
            "Generate a precious-metals weekly research report covering investment recommendations, "
            "industry views, market performance, industry tracking, and risk factors. "
            "Research scope: Spot gold, COMEX gold, the Chinese market, silver, and related non-ferrous metals. "
            "Time range: 2025-06-02 to 2025-06-08"
        )
        key, spec = select_domain(query, "auto")
        self.assertEqual(key, "precious_metals")
        self.assertEqual(spec["domain"], "Precious Metals")

    def test_explicit_etf_query_remains_etf(self) -> None:
        key, spec = select_domain(
            "Generate an ETF report on index performance, fund flows, and holdings.",
            "auto",
        )
        self.assertEqual(key, "etf")
        self.assertEqual(spec["domain"], "ETF")


if __name__ == "__main__":
    unittest.main()

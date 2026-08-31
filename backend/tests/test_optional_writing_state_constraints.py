from __future__ import annotations

import unittest

from logicrag_core.query_processing import apply_query_label_boost


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


if __name__ == "__main__":
    unittest.main()

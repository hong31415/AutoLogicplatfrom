from __future__ import annotations

import json
import unittest

from app.services.deepseek import build_prompt


class EvidencePromptWeightingTests(unittest.TestCase):
    def test_prompt_separates_primary_records_from_weighted_baseline(self) -> None:
        sections = [{"node_id": "S1", "label": "行情回顾", "order": 1, "content": "draft"}]
        materials = {
            "S1": {
                "required_materials": ["market.price"],
                "evidence_bindings": [{
                    "status": "found",
                    "provider": "Test",
                    "endpoint": "daily",
                    "instrument": "CU0",
                    "date": "2025-06-08",
                    "start_date": "2025-06-02",
                    "end_date": "2025-06-08",
                    "records": [{"date": "2025-06-03", "close": 100}],
                    "context_records": [{
                        "weight": 0.65,
                        "days_before_start": 3,
                        "record": {"date": "2025-05-30", "close": 98},
                    }],
                }],
            }
        }
        payload = json.loads(build_prompt("weekly copper report", "2025-06-08", sections, materials))
        evidence = payload["evidence_catalog"][0]
        self.assertEqual(evidence["records"][0]["date"], "2025-06-03")
        self.assertEqual(evidence["pre_period_context"][0]["weight"], 0.65)
        self.assertTrue(any("lower-weight baseline" in item for item in payload["requirements"]))


if __name__ == "__main__":
    unittest.main()

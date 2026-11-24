"""Validate exact original generation artifact bytes and public summary.

These checks verify commitments and arithmetic, not provider-side authenticity.
Independent scoring additionally uses the pinned reference-index bytes.
"""
from __future__ import annotations

import hashlib
import json
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "evidence/graphwalks/openai-first-generation-2026-11-24/original-actions-artifact.zip"
ARCHIVE_SHA = "dd7834d6f3162ab2683d5cf39a382393dea1afcd0725ab03102ea252c7b24a07"
FILES = {
    "intent.json": "95f3c7f5d458c43c8a01d472aefcc2a4f05c02951a285deb047f019b677976af",
    "plan.json": "615ca98d0f989f5c8ac11b6476d9504c246dea4bce9bf818c713f0180f44a427",
    "outcome.json": "177da4abe07c3599d00a5b27c74483b2e105c98622761a07600927098b075937",
    "scoring-evidence.json": "57974eba45d0288a881069a577de503fa4fa214d41bc083e8dd782db5f1a8dc6",
    "verification.json": "95ebd6ef8c09063a340372e7d1502b413efe0ee3ce6384d19c4600137256c0a5",
}


class FirstGenerationArchiveTests(unittest.TestCase):
    def test_exact_bytes_and_summary(self):
        self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(), ARCHIVE_SHA)
        self.assertEqual(ARCHIVE.stat().st_size, 2847)
        with zipfile.ZipFile(ARCHIVE) as archive:
            self.assertEqual(set(archive.namelist()), set(FILES))
            self.assertEqual(len(archive.namelist()), len(FILES))
            records = {}
            for name, digest in FILES.items():
                raw = archive.read(name)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
                records[name] = json.loads(raw)
        plan = records["plan.json"]
        outcome = records["outcome.json"]
        evidence = records["scoring-evidence.json"]
        verification = records["verification.json"]
        summary = json.loads((ROOT / "website/graphwalks-openai-result.json").read_text())
        source = json.loads((ROOT / "website/graphwalks-audit.json").read_text())
        reference = next(row for row in source["tasks"] if row["id"] == plan["task_id"])
        self.assertEqual(plan["prompt_sha256"], reference["prompt_sha256"])
        self.assertEqual(plan["reference_index_sha256"], source["source"]["reference_index_sha256"])
        self.assertEqual(summary["artifact_sha256"], ARCHIVE_SHA)
        self.assertEqual(summary["prompt_sha256"], plan["prompt_sha256"])
        self.assertEqual(summary["reference_index_sha256"], plan["reference_index_sha256"])
        self.assertEqual(summary["model"], outcome["model"])
        self.assertEqual(summary["task_id"], outcome["task_id"])
        self.assertEqual(summary["grade"], outcome["grade"])
        self.assertEqual(verification["grade"], outcome["grade"])
        for record in (outcome, evidence, verification, records["intent.json"]):
            self.assertEqual(record["plan_sha256"], FILES["plan.json"])
        self.assertEqual(outcome["scoring_evidence_sha256"], FILES["scoring-evidence.json"])
        self.assertEqual(evidence["answer_sha256"], outcome["answer_sha256"])
        self.assertEqual(hashlib.sha256(evidence["final_line"].encode()).hexdigest(), evidence["final_line_sha256"])
        self.assertNotEqual(evidence["answer_sha256"], evidence["final_line_sha256"])
        self.assertEqual(outcome["grade"]["reference_nodes"], reference["answer_node_count"])
        self.assertEqual(summary["input_tokens"], outcome["input_tokens"])
        self.assertEqual(summary["output_tokens"], outcome["output_tokens"])
        for field in ("external_third_party_verified", "full_answer_extraction_verified",
                      "provider_execution_independently_authenticated", "actual_billed_cost_verified",
                      "published_claim_reproduced"):
            self.assertIs(summary[field], False)
        expected = (Decimal(plan["input_usd_per_million_upper"]) * outcome["input_tokens"]
                    + Decimal(plan["output_usd_per_million_upper"]) * outcome["output_tokens"]) / 1000000
        self.assertEqual(Decimal(summary["upper_usage_cost_usd"]), expected)
        self.assertEqual(Decimal(outcome["upper_usage_cost_usd"]), expected)
        self.assertEqual(summary["reservation_usd"], plan["reservation_usd"])


if __name__ == "__main__":
    unittest.main()

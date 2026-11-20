"""Adversarial tests for source-log import, scoring, provenance and privacy."""

from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from model_claim_replay.cli import main
from model_claim_replay.core import ReplayError, load_claim
from model_claim_replay.inspect_evidence import (
    _score_summary, extract_inspect_records, hash_log_file, import_inspect_bundle,
    inspect_report_html, verify_inspect_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
CLAIM_PATH = ROOT / "claims/claude-fable-5-2-chartography.json"


def fixture_log(*, tasks=2, epochs=2, score=1, model="anthropic/claude-fable-5-2"):
    """Use Inspect's documented object fields; no official provider output is faked."""
    samples = [
        NS(id=f"licensed-task-{i}", epoch=j, error=None,
           output=NS(completion="PRIVATE MODEL OUTPUT"),
           input=[NS(role="user", content=[
               NS(type="text", text=f"PRIVATE CHART IMAGE task {i}"),
               NS(type="image", image=(
                   "data:image/png;base64,"
                   "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1Pe"
                   "AAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
               )),
           ])], target="PRIVATE GOLDEN ANSWER",
           scores={"golden_answer_scorer": NS(value={"accuracy": score}, metadata={"result": "pass" if score == 1 else "fail"})})
        for i in range(tasks) for j in range(1, epochs + 1)
    ]
    return NS(status="success", eval_=None, **{
        "eval": NS(task="chartography", model=model,
            task_args={"judge_model": "google/gemini-3.5-flash", "hf_repo": "surgeai/chartography", "split": "test"},
            config=NS(epochs=epochs),
            revision=NS(commit="3f1bf837232d3918c2cc35c6e2418c9e70d2a57b", dirty=False),
            packages={"inspect_ai": "0.3.244"}),
        "samples": samples,
        "results": NS(total_samples=tasks * epochs, completed_samples=tasks * epochs,
                     scores=[NS(scorer="golden_answer_scorer", name="accuracy", reducer="mean",
                                metrics={"mean": NS(value=float(score))})]),
    })


class InspectEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.claim = load_claim(CLAIM_PATH)

    def test_valid_subset_is_not_comparable(self):
        log = fixture_log()
        rows, header = extract_inspect_records(log, self.claim)
        summary = _score_summary(self.claim, rows, header)
        self.assertEqual((summary["successes"], summary["distinct_tasks"], summary["attempted"]), (4, 2, 4))
        self.assertEqual(summary["comparison_status"], "not_comparable")
        self.assertEqual(summary["content_fingerprinted"], 4)
        self.assertFalse(summary["coverage_complete"])
        self.assertIsNone(summary["task_cluster_bootstrap_95"])
        self.assertTrue(any("Incomplete" in reason for reason in summary["comparison_blockers"]))
        self.assertNotIn("PRIVATE MODEL OUTPUT", json.dumps(rows))
        self.assertNotIn("PRIVATE GOLDEN ANSWER", json.dumps(rows))

    def test_full_grid_never_certifies_publisher_protocol(self):
        log = fixture_log(tasks=100, epochs=10, score=1, model="claude-fable-5-2")
        rows, header = extract_inspect_records(log, self.claim)
        summary = _score_summary(self.claim, rows, header)
        self.assertTrue(summary["coverage_complete"])
        self.assertEqual(summary["observed_score"], 1)
        self.assertEqual(summary["task_cluster_bootstrap_95"], [1, 1])
        self.assertEqual(summary["comparison_status"], "not_comparable")
        self.assertTrue(any("Publisher's exact" in issue for issue in summary["comparison_blockers"]))

    def test_inconsistent_content_across_epochs_is_rejected(self):
        log = fixture_log()
        log.samples[1].target = "DIFFERENT ANSWER"
        rows, header = extract_inspect_records(log, self.claim)
        with self.assertRaisesRegex(ReplayError, "differs across repeated epochs"):
            _score_summary(self.claim, rows, header)

    def test_unresolved_chart_reference_is_explicitly_unpinned(self):
        log = fixture_log()
        log.samples[0].input[0].content[1].image = "/tmp/local-chart.png"
        rows, header = extract_inspect_records(log, self.claim)
        summary = _score_summary(self.claim, rows, header)
        self.assertEqual(summary["content_fingerprinted"], 3)
        self.assertTrue(any("byte-bound input fingerprints" in b for b in summary["comparison_blockers"]))

    def test_duplicate_epoch_refused(self):
        log = fixture_log()
        log.samples.append(copy.deepcopy(log.samples[0]))
        with self.assertRaisesRegex(ReplayError, "Duplicate"):
            extract_inspect_records(log, self.claim)

    def test_fractional_binary_score_refused(self):
        log = fixture_log(score=0.5)
        with self.assertRaisesRegex(ReplayError, "exactly 0, 1"):
            extract_inspect_records(log, self.claim)

    def test_boolean_score_refused(self):
        log = fixture_log(score=True)
        with self.assertRaisesRegex(ReplayError, "exactly 0, 1"):
            extract_inspect_records(log, self.claim)

    def test_score_metadata_conflict_refused(self):
        log = fixture_log(score=1)
        log.samples[0].scores["golden_answer_scorer"].metadata["result"] = "fail"
        with self.assertRaisesRegex(ReplayError, "contradicts"):
            extract_inspect_records(log, self.claim)

    def test_wrong_task_or_unsuccessful_log_refused(self):
        log = fixture_log()
        getattr(log, "eval").task = "unrelated"
        with self.assertRaisesRegex(ReplayError, "chartography task"):
            extract_inspect_records(log, self.claim)
        log.status = "error"
        with self.assertRaisesRegex(ReplayError, "not success"):
            extract_inspect_records(log, self.claim)

    def test_unscored_excluded_and_reported(self):
        log = fixture_log()
        log.samples[0].scores["golden_answer_scorer"].value = {"accuracy": math.nan}
        rows, header = extract_inspect_records(log, self.claim)
        summary = _score_summary(self.claim, rows, header)
        self.assertEqual(summary["unscored"], 1)
        self.assertEqual(summary["assessed"], 3)
        self.assertEqual(summary["observed_denominator"], 3)

    def test_header_mean_mismatch_refused_on_full_grid(self):
        log = fixture_log(tasks=100, epochs=10)
        log.results.scores[0].metrics["mean"].value = 0.5
        rows, header = extract_inspect_records(log, self.claim)
        with self.assertRaisesRegex(ReplayError, "disagrees"):
            _score_summary(self.claim, rows, header)

    def test_all_unscored_aggregate_nan_has_no_observed_accuracy(self):
        log = fixture_log()
        for sample in log.samples:
            sample.scores["golden_answer_scorer"].value = {"accuracy": math.nan}
            sample.scores["golden_answer_scorer"].metadata = {"result": "unscored"}
        log.results.scores[0].metrics["mean"].value = math.nan
        rows, header = extract_inspect_records(log, self.claim)
        summary = _score_summary(self.claim, rows, header)
        self.assertIsNone(header["logged_mean"])
        self.assertIsNone(summary["observed_score"])
        self.assertEqual(summary["assessed"], 0)
        self.assertEqual(summary["unscored"], 4)
        self.assertEqual(summary["comparison_status"], "not_comparable")

    def test_infinite_aggregate_refused_even_if_all_unscored(self):
        log = fixture_log()
        log.results.scores[0].metrics["mean"].value = math.inf
        with self.assertRaisesRegex(ReplayError, "aggregate accuracy/mean is invalid"):
            extract_inspect_records(log, self.claim)

    def test_incomplete_and_missing_header_never_compared(self):
        log = fixture_log()
        log.results.scores = []
        rows, header = extract_inspect_records(log, self.claim)
        summary = _score_summary(self.claim, rows, header)
        self.assertIsNone(summary["reference_protocol_flags"]["logged_mean"])
        self.assertTrue(any("No original" in issue for issue in summary["comparison_blockers"]))

    def test_bundle_verification_source_binding_tamper_and_html_escaping(self):
        log = fixture_log()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "source.eval"
            raw.write_bytes(b"inspect fixture placeholder - genuine API parsing bypassed only in test")
            out = root / "evidence"
            summary = import_inspect_bundle(CLAIM_PATH, raw, out, log=log)
            self.assertEqual(summary["attempted"], 4)
            audited = verify_inspect_bundle(CLAIM_PATH, out, source_log=raw)
            self.assertTrue(audited["source_log_checked"])
            output = json.dumps(json.loads((out / "run.json").read_text())) + (out / "results.jsonl").read_text()
            for private in ("PRIVATE MODEL OUTPUT", "PRIVATE CHART IMAGE", "PRIVATE GOLDEN ANSWER"):
                self.assertNotIn(private, output)
            self.assertEqual(main(["verify", str(out), "--claim", str(CLAIM_PATH), "--source-log", str(raw)]), 0)
            html_out = root / "report.html"
            self.assertEqual(main(["report", str(out), "--claim", str(CLAIM_PATH),
                                   "--format", "html", "--output", str(html_out)]), 0)
            self.assertIn("not_comparable", html_out.read_text())
            self.assertIn("No external scripts", html_out.read_text())
            with self.assertRaisesRegex(ReplayError, "already exists"):
                import_inspect_bundle(CLAIM_PATH, raw, out, log=log)
            raw.write_bytes(b"altered")
            with self.assertRaisesRegex(ReplayError, "no longer matches"):
                verify_inspect_bundle(CLAIM_PATH, out, source_log=raw)
            with (out / "results.jsonl").open("ab") as stream:
                stream.write(b"\n")
            with self.assertRaisesRegex(ReplayError, "changed"):
                verify_inspect_bundle(CLAIM_PATH, out)

    def test_record_score_tampering_rejected_even_with_updated_hash(self):
        log = fixture_log()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "test.eval"
            source.write_bytes(b"fixture")
            out = root / "evidence"
            import_inspect_bundle(CLAIM_PATH, source, out, log=log)
            import hashlib
            rows = (out / "results.jsonl").read_text().splitlines()
            r = json.loads(rows[0])
            r["status"] = "pass"
            r["score"] = 0  # inconsistent with pass, even under a newly forged hash
            rows[0] = json.dumps(r)
            (out / "results.jsonl").write_text("\n".join(rows) + "\n")
            meta = json.loads((out / "run.json").read_text())
            meta["results_sha256"] = hashlib.sha256((out / "results.jsonl").read_bytes()).hexdigest()
            (out / "run.json").write_text(json.dumps(meta))
            with self.assertRaisesRegex(ReplayError, "contradicts"):
                verify_inspect_bundle(CLAIM_PATH, out)

    def test_report_escapes_untrusted_model_label(self):
        log = fixture_log(model="<script>alert(1)</script>")
        records, header = extract_inspect_records(log, self.claim)
        summary = _score_summary(self.claim, records, header)
        summary["source_log_sha256"] = "0" * 64
        markup = inspect_report_html(self.claim, summary)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", markup)
        self.assertNotIn("<script>alert(1)</script>", markup)

    def test_original_log_path_is_not_serialized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "unique-private-location.eval"
            source.write_bytes(b"placeholder")
            out = root / "run"
            import_inspect_bundle(CLAIM_PATH, source, out, log=fixture_log())
            content = (out / "run.json").read_text()
            self.assertNotIn(str(root), content)
            self.assertIn('"source_log_filename":"unique-private-location.eval"', content)


if __name__ == "__main__":
    unittest.main()

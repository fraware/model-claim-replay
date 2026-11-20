"""Unit and adversarial tests of scoring, manifests, and local integrity."""

import json
import tempfile
import unittest
from pathlib import Path

from model_claim_replay.cli import main
from model_claim_replay.core import ReplayError, evaluate_records, load_claim, read_jsonl, task_data, verify_bundle, wilson_interval

ROOT = Path(__file__).resolve().parents[1]
CLAIM = ROOT / 'claims/demo-text-exact-match.json'
TASKS = ROOT / 'examples/demo-tasks.jsonl'
RESPONSES = ROOT / 'examples/demo-responses.jsonl'


class EvidenceTests(unittest.TestCase):
    def test_manifest_and_dataset_are_pinned(self):
        claim = load_claim(CLAIM)
        self.assertEqual(len(task_data(claim, TASKS)), 3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'tasks.jsonl'
            path.write_bytes(TASKS.read_bytes() + b'\n')
            with self.assertRaisesRegex(ReplayError, 'SHA-256'):
                task_data(claim, path)

    def test_published_claim_blocked(self):
        claim = load_claim(ROOT/'claims/claude-fable-5-2-chartography.json')
        self.assertEqual(claim['reported_score'], 0.734)
        with self.assertRaisesRegex(ReplayError, 'no pinned dataset'):
            task_data(claim, TASKS)

    def test_synthetic_score_is_not_claim_reproduction(self):
        claim = load_claim(CLAIM)
        summary = evaluate_records(claim, task_data(claim, TASKS),
            [{'id': r['id'], 'status': 'ok', 'output': r['output']} for r in read_jsonl(RESPONSES)], model='fixture-model', run_kind='imported')
        self.assertEqual(summary['successes'], 2)
        self.assertEqual(summary['failures'], 1)
        self.assertEqual(summary['observed_score'], 2/3)
        self.assertEqual(summary['comparison_status'], 'not_comparable')

    def test_wilson_endpoints_and_empty(self):
        self.assertIsNone(wilson_interval(0, 0))
        low, high = wilson_interval(2, 3)
        self.assertTrue(0 < low < 2/3 < high < 1)
        self.assertEqual(wilson_interval(0, 1)[0], 0)
        self.assertEqual(wilson_interval(1, 1)[1], 1)

    def test_errors_do_not_count_as_wrong_answers(self):
        claim = load_claim(CLAIM)
        summary = evaluate_records(claim, task_data(claim, TASKS),
            [{'id':'one','status':'ok','output':'alpha'}, {'id':'two','status':'error'}],
            model='fixture-model', run_kind='api')
        self.assertEqual((summary['assessed'], summary['errors'], summary['attempted']), (1,1,2))
        self.assertEqual(summary['observed_score'], 1)
        self.assertEqual(summary['comparison_status'], 'not_comparable')

    def test_duplicate_response_id_fails(self):
        claim = load_claim(CLAIM)
        with self.assertRaisesRegex(ReplayError, 'duplicate'):
            evaluate_records(claim, task_data(claim, TASKS), [
                {'id':'one','status':'ok','output':'alpha'},
                {'id':'one','status':'ok','output':'alpha'}],
                model='fixture-model', run_kind='imported')

    def test_unknown_response_id_fails(self):
        claim = load_claim(CLAIM)
        with self.assertRaisesRegex(ReplayError, 'unknown'):
            evaluate_records(claim, task_data(claim, TASKS), [
                {'id':'unknown','status':'ok','output':'alpha'}],
                model='fixture-model', run_kind='imported')

    def test_end_to_end_cli_and_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'run'
            self.assertEqual(main(['evaluate','--claim',str(CLAIM),'--tasks',str(TASKS),
                '--responses',str(RESPONSES),'--model','fixture-model','--out',str(out)]), 0)
            summary = verify_bundle(CLAIM, TASKS, out)
            self.assertEqual(summary['assessed'], 3)
            report = Path(tmp)/'report.html'
            self.assertEqual(main(['report',str(out),'--claim',str(CLAIM),
                '--tasks',str(TASKS),'--output',str(report)]),0)
            content = report.read_text()
            self.assertIn('66.7%',content)
            self.assertIn('self-reported',content)
            self.assertEqual(main(['evaluate','--claim',str(CLAIM),'--tasks',str(TASKS),
                '--responses',str(RESPONSES),'--model','fixture-model','--out',str(out)]),2)
            (out/'results.jsonl').write_text((out/'results.jsonl').read_text()+'\n')
            with self.assertRaisesRegex(ReplayError,'modified'):
                verify_bundle(CLAIM,TASKS,out)

    def test_escaped_html_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            from model_claim_replay.cli import _report_page
            claim=load_claim(CLAIM)
            summary=evaluate_records(claim, task_data(claim,TASKS),[{'id': r['id'], 'status': 'ok', 'output': r['output']} for r in read_jsonl(RESPONSES)], model='<script>x</script>',run_kind='imported')
            html=_report_page(claim,summary)
            self.assertIn('&lt;script&gt;x&lt;/script&gt;',html)
            self.assertNotIn('<script>x</script>',html)


if __name__ == '__main__':
    unittest.main()

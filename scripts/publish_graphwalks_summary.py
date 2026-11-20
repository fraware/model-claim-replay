"""Publish a content-limited, independently derivable GraphWalks explorer snapshot.

Source must be the 200-record reference index from our byte-verified
Parquet audit. Exports no raw prompts, model outputs or correct answer nodes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

INDEX_SHA256 = "250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee"
PARQUET_SHA256 = "537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911"
REVISION = "be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7"


def build_snapshot(raw: bytes) -> dict:
    """Verify the original index and derive non-sensitive task statistics."""
    if hashlib.sha256(raw).hexdigest() != INDEX_SHA256:
        raise ValueError("Reference index digest differs from the verified source")
    data = [json.loads(s) for s in raw.splitlines() if s.strip()]
    if len(data) != 200 or len({x['id'] for x in data}) != 200:
        raise ValueError("Verified candidate cohort must have 200 unique BFS IDs")
    tasks = []
    for row in data:
        if row.get('problem_type') != 'bfs':
            raise ValueError("Non-BFS reference encountered")
        chars, answer = row.get('prompt_chars_actual'), row.get('answer_nodes')
        if type(chars) is not int or chars <= 0 or not isinstance(answer, list):
            raise ValueError("Malformed reference item")
        if len(row['prompt_sha256']) != 64 or not all(c in '0123456789abcdef' for c in row['prompt_sha256']):
            raise ValueError("Missing prompt digest")
        tasks.append({
            'id': row['id'],
            'source_row_index': row['source_row_index'],
            'prompt_chars': chars,
            'answer_node_count': len(answer),
            'prompt_sha256': row['prompt_sha256'],
        })
    lengths = sorted(t['prompt_chars'] for t in tasks)
    lower = sum(c < 1_000_000 for c in lengths)
    return {
        'schema_version': 'graphwalks-public-explorer-v1',
        'source': {
            'dataset': 'openai/graphwalks',
            'revision': REVISION,
            'parquet_sha256_verified': PARQUET_SHA256,
            'reference_index_sha256': INDEX_SHA256,
            'audit_run': 'https://github.com/fraware/model-claim-replay/actions/runs/44746523023',
        },
        'summary': {
            'source_rows': 400,
            'bfs_tasks': len(tasks),
            'shorter_tasks': lower,
            'longer_tasks': len(tasks)-lower,
            'length_display_threshold_characters': 1_000_000,
            'min_prompt_chars': lengths[0],
            'median_prompt_chars': (lengths[99] + lengths[100])/2,
            'max_prompt_chars': lengths[-1],
            'total_prompt_chars': sum(lengths),
        },
        'disclaimer': 'Verified public candidate dataset only. Google used 200 GraphWalks tasks, but exact revision and row IDs have not been established. No model inference has been executed; prompt lengths are characters, not tokens.',
        'tasks': tasks,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error('Refusing to overwrite an existing website audit snapshot')
    obj = build_snapshot(args.index.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(obj, separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')
    print('Generated public-data explorer for', len(obj['tasks']), 'byte-verified BFS tasks')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

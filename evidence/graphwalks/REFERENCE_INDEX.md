# Pinned GraphWalks reference archive

The [original ZIP](verified-bfs-reference-index.zip) is the byte-identical public GitHub Actions artifact 14632384711 from [source audit run 44746523023](https://github.com/fraware/model-claim-replay/actions/runs/44746523023). It contains the 200-task BFS reference index and source-audit manifest, with no full prompt text or private provider answers. The original dataset is [openai/graphwalks](https://huggingface.co/datasets/openai/graphwalks), pinned at revision `be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7`. The upstream dataset metadata identifies the license as MIT; the source audit records that metadata, not a separate legal assessment.

- Archive size: 881,178 bytes.
- Archive SHA-256: `cf2d078035f3a4fe5a93aeaf8cf06f1c170751bc3e4fc2f2cd68a66a380bb9fe`.
- Reference index SHA-256: `250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee`.

From the repository root, install the base package and run:

```bash
python -m pip install -e .
python scripts/verify_archived_evidence.py
```

No model key, source download, optional dependency or inference is needed for the verification command. The pinned reference archive includes benchmark answer nodes. Keep these reference records separate from prompts sent to models; the verifier is not an evaluation runner. The two original experiments remain distinct; seven campaign answers and the pilot's disclosed answer are recomputed, one campaign parser-failure record is withheld, and eight selected campaign tasks are context-blocked. The checks do not prove provider origin, faithful full-answer extraction or publisher reproduction.

For independent regeneration from the pinned Parquet, follow the [source audit guide](../../docs/GRAPHWALKS.md).

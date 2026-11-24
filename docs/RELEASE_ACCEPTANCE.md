# Release acceptance and external validation

Decision record, 23 November 2026. GitHub Trending Daily is an aspiration; never purchase stars, solicit reciprocal stars, or misrepresent evaluation findings. No external test sessions or paid model generations are claimed here.

## Six release gates

| Gate | Acceptance criterion | Current evidence |
| --- | --- | --- |
| Real-model experiment | At least one independently initiated successful generation on a prespecified source-bound task, with model ID, protocol, usage, finish state and original grader recorded. A single task is a diagnostic, never a population estimate. | Blocked: explicit dispatch and spending approval pending. |
| Independent scoring and inspectability | A third party recomputes the diagnostic score from permitted original responses and references, or the project documents why raw outputs are unavailable; a redacted consistency check alone does not qualify as independent rescoring. Every task outcome and exclusion is accounted for. | Partial: 200-task algorithmic control, provider token counts, public receipts; no model scores. |
| Installation | Wheel and clean-environment installation, offline CLI demonstration, desktop/mobile website tests; at least four of five independent users complete onboarding in five minutes or less, with no private credentials needed. | Automated coverage exists; external sessions not yet performed. |
| External testing | Five independent developers or evaluation researchers, recruited for task-relevant expertise. Record all attempts including failures, time to first report, usability issues, and whether they would use the tool on another claim. No reward tied to stars or positive feedback. | Not started. |
| Differentiation | Review existing execution frameworks and claim databases; at least three external testers identify a task they would use this workflow for, with a specific reason. No blanket novelty claim. | Initial desk review below; user validation outstanding. |
| Launch timing and distribution | Release candidate passes preceding gates; share a source-linked finding with a minimal replay command and an explicit limitation. Choose a relevant verified event or fresh model release, and measure organic adoption at 24h and 7d. | Candidate window below, conditional on readiness. |

The thresholds are predeclared operational targets, not statistically representative market evidence. A verified single-task result does not establish reproduction of a publisher aggregate. A public artifact must state whether scoring is independently recomputable.

## First GraphWalks experiment

The [Google methodology PDF](https://deepmind.google/models/evals-methodology/gemini-4-neon/) (printed pp. 1, 3, 5) identifies a 200-problem long-context cohort, a high-thinking Gemini API protocol, and a 95.2% BFS F1 result. It does not enumerate the source-row identities or give an exact output/continuation configuration for GraphWalks. The [Epoch AI review](https://epoch.ai/benchmarks/graphwalks/review) independently flags public task/solution availability, version drift and long-context output constraints.

Preserve the existing pinned selection policy. Run one feasible shorter prompt at xhigh, with a 65,536 output-token allowance and a proposed $5 reservation ceiling, only after explicit financial authorization and fresh provider token counting. Do not rerun a failed paid job with reused approval. Record incomplete, filtered, and uncertain outcomes as such. Do not extrapolate from one task or substitute another model for the Gemini claim. Resolve publisher dataset identities, prompt construction, decoding configuration and grading before a full claim replication.

## Prior-art and differentiation review

Primary project documentation reviewed on 23 November 2026. This is a functional comparison, not an exhaustive market survey.

| Existing project | Verified overlap | Position for Model Claim Replay |
| --- | --- | --- |
| [Inspect AI](https://inspect.aisi.org.uk/) | Evaluation harness and scoring | Integrate official logs; preserve claim-specific comparability and evidence. |
| [HELM](https://crfm.stanford.edu/helm/) | Reproducible and transparent evaluation | Focus on a specific external publisher claim and its execution prerequisites. |
| [Lighteval](https://huggingface.co/docs/lighteval/main/en/index) | Benchmark execution and result storage | Avoid duplicating general-purpose execution engines. |
| [Artificial Analysis](https://artificialanalysis.ai/methodology/) | Independent model evaluation across capability, price and performance | Focus on source-bound reproducibility of a named claim, not ranking models. |
| [AI Eval Observatory](https://observatory.srmdn.com/methodology/) | Provenance-aware claims, methods and evidence levels | Claim curation alone is insufficient differentiation; emphasize runnable recipes and auditable outcomes. |
| [Seriously, Models?](https://github.com/fabriziosalmi/seriously-models-verified) | Large-scale source-pinned mechanical verification of published benchmark statements | Source verification already exists. Complement it through execution and scoring of individual claims. |
| [Frontier Log](https://frontierlog.ai/model/gemini-4-neon) | Model-launch records, benchmark sources and protocol context, including Neon GraphWalks | Avoid building another launch database. |
| [FalkorDB GraphWalks](https://github.com/FalkorDB/GraphWalks) | GraphWalks runner and algorithm-assisted proxy | Treat the existing proxy as related work, distinguish direct model generation from algorithmic controls. |

The proposed differentiator is a practical workflow from a specific published claim to pinned source data, execution-feasibility checks, a budgeted run, task-level scoring and an explicit comparison verdict. Several adjacent tools already support parts of this workflow. External feedback must establish whether the integration saves meaningful effort.

## External testing protocol

Send the [onboarding feedback form](https://github.com/fraware/model-claim-replay/issues/new?template=developer-replay-feedback.yml) to five relevant independent testers. Ask them to start from the repository homepage, run the offline demo on their own machine, open its report, then inspect the public GraphWalks finding and identify its scope. Observe or request elapsed time, errors, and their own interpretation. Never request secrets, raw private logs, or positive public endorsements. Record unsuccessful sessions alongside successful ones.

## Timing and distribution

The [official NeurIPS schedule](https://neurips.cc/Conferences/2026/Dates) lists Sydney expo day December 6, tutorials December 7, main conference December 8–10, and workshops December 11–12. This is a potential window for relevant evaluation researchers and developers. Use the preconference period for a small external pilot. Launch only when the gates are satisfied; alternatively release the feasibility audit as a narrowly labeled research note, with no reproduction claim.

For a qualifying launch, publish the evidence and reproducible instructions first. Share one source-linked technical post, offer the offline reproduction to interested researchers, and invite corrections. Track GitHub unique visitors/clones where available, genuine stars, forks, independent replay reports and issue feedback at 24 hours and seven days. No outreach or adoption has been measured by this document.

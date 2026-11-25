# Release acceptance and external validation

[Documentation home](README.md) · [Roadmap](ROADMAP.md)

Maintainer decision record; not the first-time user guide.

Decision record, 23 November 2026. GitHub Trending Daily is an aspiration; never purchase stars, solicit reciprocal stars, or misrepresent evaluation findings. Updated 24 November 2026: the one-task OpenAI diagnostic and separate 16-task campaign completed; external test sessions and third-party verification remain outstanding.

## Six release gates

| Gate | Acceptance criterion | Current evidence |
| --- | --- | --- |
| Real-model experiment | At least one independently initiated successful generation on a prespecified source-bound task, with model ID, protocol, usage, finish state and original grader recorded. A single task is a diagnostic, never a population estimate. | Passed for one diagnostic: [actual OpenAI generation](https://github.com/fraware/model-claim-replay/actions/runs/45398852989), F1 1.0 on one prespecified task. |
| Independent scoring and inspectability | A third party recomputes the diagnostic score from permitted original responses and references. If raw responses are unavailable, document the access restriction and keep this gate open until authorized independent rescoring occurs; redacted consistency checks alone do not qualify. Every task outcome and exclusion is accounted for. | Partial: exact disclosed final-line score recomputed in the workflow and separately from downloaded artifacts; seven of eight graded campaign scores independently recomputed from disclosed lines. The withheld parser failure, full-answer extraction and external third-party verification remain outstanding. |
| Installation | Wheel and clean-environment installation, offline CLI demonstration, desktop/mobile website tests; at least four of five independent users complete onboarding in five minutes or less, with no private credentials needed. | Cross-platform wheel installation, offline evidence checks and public production browser checks passed in CI; external sessions not yet performed. |
| External testing | Five independent developers or evaluation researchers, recruited for task-relevant expertise. Record all attempts including failures, time to first report, usability issues, and whether they would use the tool on another claim. No reward tied to stars or positive feedback. | Not started. |
| Differentiation | Review existing execution frameworks and claim databases; at least three external testers identify a task they would use this workflow for, with a specific reason. No blanket novelty claim. | Initial desk review below; user validation outstanding. |
| Launch timing and distribution | Release candidate passes preceding gates; share a source-linked finding with a minimal replay command and an explicit limitation. Choose a relevant verified event or fresh model release, and measure organic adoption at 24h and 7d. | Candidate window below, conditional on readiness. |

The thresholds are predeclared operational targets, not statistically representative market evidence. A verified single-task result does not establish reproduction of a publisher aggregate. A public artifact must state whether scoring is independently recomputable.

## Provider policy and first GraphWalks experiment

OpenAI is now the default provider. The separate GPT-6.2 Sol one-task diagnostic uses the OpenAI Responses API and uses a safe default `PREFLIGHT_ONLY` for token counting. Select `AUTHORIZE_PAID_OPENAI` explicitly in the workflow dropdown with a positive USD ceiling for actual generation. It does not substitute for the historical Gemini-specific investigation. See [the automation inventory](WORKFLOWS.md) for the workflow lifecycle. The source-bound preflight and first paid diagnostic have passed; one task scored F1 1.0 under the disclosed final-line calculation. Separate `PUBLISH_FINAL_LINE` consent authorizes a restricted score-relevant final-line export for offline recomputation. Independent rescoring of the disclosed line remains conditional on extraction fidelity; if the full original answer is unavailable, the original-response verification gate stays open.

The [Google methodology PDF](https://deepmind.google/models/evals-methodology/gemini-4-neon/) (printed pp. 1, 3, 5) identifies a 200-problem long-context cohort, a high-thinking Gemini API protocol, and a 95.2% BFS F1 result. It does not enumerate the source-row identities or give an exact output/continuation configuration for GraphWalks. The [Epoch AI review](https://epoch.ai/benchmarks/graphwalks/review) independently flags public task/solution availability, version drift and long-context output constraints.

The historical first-diagnostic plan was to run one feasible shorter prompt at xhigh, with a 65,536 output-token allowance and a proposed $5 reservation ceiling, only after explicit financial authorization and fresh provider token counting. Do not rerun a failed paid job with reused approval. The separately recorded one-time first-generation exception is triggered only on the first introduction of its fixed authorization record on main. The reusable workflow remains manual; the exception cannot be reused by editing, removing/reintroducing or rerunning its record under ordinary Git history. Record incomplete, filtered, and uncertain outcomes as such. Do not extrapolate from one task or substitute another model for the Gemini claim. Resolve publisher dataset identities, prompt construction, decoding configuration and grading before a full claim replication.

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

Use the [pinned reviewer guide](REVIEWER_GUIDE.md) and its separate developer and independent evidence-review forms. Maintainer-run verification is not external review.

Use the deployed website and the installed wheel or Git checkout. Testers should start in a clean environment where possible; the timer starts when opening the repository quickstart and stops when the generated HTML report opens, including installation time. Record OS, Python version, installation path, whether all steps succeeded, and the elapsed time. A non-attempt is recorded separately and excluded from the timed completion denominator; recruit replacements until five attempts exist. The tester should then inspect the source-task example and, optionally, use the browser checker on the locally generated bundle. Ask the tester to describe what was established by each check before explaining the intended answer. Never classify a maintainer's automated test or a simulated session as external feedback.

Send the [onboarding feedback form](https://github.com/fraware/model-claim-replay/issues/new?template=developer-replay-feedback.yml) to five relevant independent testers. Ask them to start from the repository homepage, run the offline demo on their own machine, open its report, then inspect the public GraphWalks finding and identify its scope. Observe or request elapsed time, errors, and their own interpretation. Never request secrets, raw private logs, or positive public endorsements. Record unsuccessful sessions alongside successful ones.

### Historical Gemini pilot dispatch checklist

Open the [manual paid GraphWalks diagnostic workflow](https://github.com/fraware/model-claim-replay/actions/workflows/graphwalks-paid-pilot.yml) on main. An authorized maintainer must select these exact inputs:

- `tasks`: `1`
- `output_tokens`: `65536`
- `max_spend_usd`: `5`
- `approval`: `AUTHORIZE_PAID_GEMINI`

The runner independently verifies the source, obtains fresh provider input counts and checks the reservation before generation. The earlier 355,124-token measurement is a planning observation, not a charge or guarantee of the fresh count. Record the workflow run ID, actual completion state, artifact commitments, usage and limitations. Do not retry an ambiguous paid request or reuse approval through the Actions rerun control. A new explicit dispatch is needed after reviewing prior charges and evidence. No such diagnostic is asserted to have run.

## Timing and distribution

The [official NeurIPS schedule](https://neurips.cc/Conferences/2026/Dates) lists Sydney expo day December 6, tutorials December 7, main conference December 8–10, and workshops December 11–12. This is a potential window for relevant evaluation researchers and developers. Use the preconference period for a small external pilot. Launch only when the gates are satisfied; alternatively release the feasibility audit as a narrowly labeled research note, with no reproduction claim.

For a qualifying launch, publish the evidence and reproducible instructions first. Share one source-linked technical post, offer the offline reproduction to interested researchers, and invite corrections. Track GitHub unique visitors/clones where available, genuine stars, forks, independent replay reports and issue feedback at 24 hours and seven days. No outreach or adoption has been measured by this document.

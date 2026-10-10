# Increment 8: offline evaluation preparation and replay

Committed and pushed as `953a4bf` on October 10, 2026 with the user's approval. Increment 7 was committed and pushed as `c6db1c6`.

## Functionality

One offline evaluation kit: validate a synthetic family-split corpus, prepare exact app prompts/run templates, replay unmodified outputs through application validation, attach output-bound human reviews, and compare eligible base/adapter bundles under matched conditions. CLI: `scripts/evaluate.py`; procedure and rubric: [evaluation.md](evaluation.md).

The starter corpus has 18 assistant-authored, unreviewed cases, six per split. These are inputs, not gold fine-tuning completions, actual outings or a sufficient benchmark. Family separation is declared before variants; exact duplicates and shape/selection errors are checked. Semantic family leakage and useful coverage require human review and expansion.

Reports distinguish application acceptance from schema/constraint/policy/exact-repeat checks and human grounding/suitability/screen-light/adaptation. Failed replies stay in denominators; missing measurements are not zero. Case/method/dataset/output hashes, actual target/checkpoint metadata, decoding, runtime lifecycle and software versions guard against incompatible artifacts. Fixture scores cannot support a model comparison. Comparison requires reviewed, complete held-out provider captures and makes no promotion decision. Metadata/review authenticity remains self-attested, not independently proven.

The follow-up service and offline scorer now share the same output acceptance function. No prompt, model, application restriction, data gate or inference setting was changed. All generated artifacts are restricted to ignored `.data/evaluation/`, with no overwrite. No secret/environment file is loaded or SDK client initialized.

## Verification

363 offline backend tests pass, including 55 new evaluation tests. New tests cover the seed split/provenance, exact app prompts, timestamp/source ordering, duplicate/family errors, missing/bad/repeated/prohibited replies, hash binding, strict metadata, every-case coverage, semantic review applicability, missing metrics, fixture exclusion and comparison matching. CLI tests forbid hosted SDK imports, network connection and `.env` reads. Local `validate` and development `prepare` commands passed with zero hosted requests. Ruff lint/format and `pip check` pass.

Frontend code is unchanged. Its last verified suite remains 126 tests and four fixture-based Edge checks; these were not rerun as a new physical-phone or outdoor check. No Tinker/Atlas/Sentry request, training job, Render deployment or extra spend occurred. The existing three-request reservation ledger remains untouched.

## Remaining boundaries

At this increment's verification boundary an accepted live `follow-up-v2` was pending. A separately approved single follow-up passed during increment 9; see [the updated evidence](live-smoke-2026-10-10.md). Training still requires reviewed data and a separate training/evaluation budget. This evaluation-tooling increment establishes neither model accuracy nor Tinker prize improvement. Physical-phone, outdoor evidence and submission assets remain pending.

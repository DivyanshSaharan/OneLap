# Offline evaluation kit

This kit prepares inputs and replays captured replies. It **never calls Tinker, Atlas or Sentry**, loads `.env`, trains a model, changes approval gates or resets the spend ledger. No hosted evaluation or training has happened. The revised follow-up still needs an accepted live result before a training pilot.

## Starter dataset, not training data or field evidence

`datasets/onelap-seed-v1.json` contains 18 assistant-authored synthetic cases: six training-design seeds, six development cases and six held-out cases. Nine scenario families were assigned to splits before their two variants were written. A family has one assignment; duplicate case IDs, identical inputs, unassigned families and inconsistent source selections are rejected. This checks declared separation and exact duplicates, not semantic leakage between related families.

The seeds are explicitly **unreviewed**. There are no gold assistant completions, actual outings or friend feedback in this file. Its six training-design cases are not a fine-tuning dataset. Human review and expansion toward the plan's 80–100 training examples, 20 development cases and 30 held-out cases remain pending. Small seed splits cannot establish generalization or statistical significance.

Human reviewers should check plausibility, privacy, useful coverage and family overlap, then freeze the version before capturing outputs. Only after real review may `review_status` become `human_reviewed` with a non-identifying reviewer label. This changes the dataset digest, so prepare new manifests afterwards. A label is an attestation, not proof that review occurred.

Use development cases for prompt iteration. Do not inspect held-out model replies to tune prompts, targets or hyperparameters. Do not move failed held-out cases into training. The earlier smoke-test cases diagnosed a prompt defect; they are not held-out evaluation evidence. Public test inputs are not secret or a guarantee against contamination.

## Commands

From the repository root in PowerShell, with development dependencies installed:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate.py validate
.\.venv\Scripts\python.exe scripts\evaluate.py prepare --split dev --output .data\evaluation\dev-manifest.json
```

`validate` reports hashes, review status and split sizes without writing anything. `prepare` exports the exact application messages, per-case input hashes, semantic checklists and an incomplete `run_template`. It defaults to `origin: fixture`, all cases `not_run` and missing measurements/reviews. Nothing is sampled. The template's example run ID/date must be replaced for an actual capture.

Save only the `run_template` object as a separate run JSON file when filling it. Preserve every case exactly once, including rejected replies, provider failures and timeouts. `provider_capture` is permitted only for genuine, separately authorized samples; handwritten/demo replies must remain `fixture`. The schema permits one raw reply **or** one explicit failure, not both. For an app-rejected model reply, retain its unmodified raw text with `error: null`; the evaluator computes the rejection. Never silently repair model output, omit bad cases, resample until success or call a template a baseline.

Record the actual model, base/adapter target, exact adapter checkpoint path and training-data digest where applicable. Preserve the manifest's dataset/method/input hashes. Record actual decoding and execution conditions: serial requests, shared client or cold client per case, Python/Tinker/tokenizer-library versions. `latency_ms` is wall time for the provider call including any setup, not model-only latency or UI/network round-trip latency. Mark unavailable measurements `null`, not zero. Count actual returned token IDs; do not estimate tokens from characters. `estimated_reserved_usd` is the per-request ledger reservation, never actual billing. A timed-out request can still incur a charge.

This increment has **no paid capture runner**. Capturing a baseline, repeating live integration, training an adapter or exporting telemetry needs separate approval with data, request and spending boundaries. The previous three-request smoke allowance is used up. Do not bypass gates or reset counters to create a bundle.

Replay an existing bundle locally:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate.py score --run .data\evaluation\dev-run.json --output .data\evaluation\dev-score.json
```

The input schema is in `backend/onelap/evaluation_models.py`. JSON artifacts are bounded to 4 MiB; duplicate JSON keys, malformed metadata and mismatched hashes fail closed. Generated artifacts must stay under ignored `.data/evaluation/` and existing files are never overwritten. Exit 0 means the artifact is valid, **not** that its model succeeded. Exit 2 means artifact validation/comparison failed; errors never echo artifact contents. Rejected raw replies and review rationale stay in the ignored run bundle, not the score report. Review all exported reports before public sharing, including IDs and reviewer labels.

## What deterministic scores mean

The application output validators are reused, including one shared follow-up validation function used by both the service and evaluator. No stricter or more forgiving evaluator-only model acceptance rule is introduced.

- **Schema:** short plain-text fields, strict JSON/types, known values, camera false and phone use disabled. Missing/malformed replies fail this check.
- **Constraints:** minutes, setting, conditions and focus match the request/source exactly.
- **Policy:** existing conservative prohibited-keyword check. A mismatch stops the pipeline before policy checking.
- **Repetition:** follow-up instruction is not a normalized exact match to a selected prior title/instruction. Paraphrases can pass and need human review.
- **Application acceptance:** all applicable app checks pass. Its denominator includes every case, failures and `not_run` entries. Mission and follow-up totals are also reported separately.

Each staged check includes passed/checked/total counts. A 100% rate among three checked outputs is not six successful cases. No single "accuracy" number combines schema, restrictions and semantic quality.

## Human rubric: `onelap-human-v1`

Review the exact raw reply beside the request, primary observation, optional prior context and case-specific checklist. Judge the reflection **and** mission, not just the structured selection fields. Use the same reviewer/procedure for both models where possible; document whether review was blind, disagreement and any adjudication. This tool does not enforce blinding or establish reviewer independence.

| Dimension | 0 — fails | 1 — partial | 2 — fully meets |
| --- | --- | --- | --- |
| Grounding | Invents surroundings, causes, species, weather, feelings, progress or safety | Generic/vague, or uncertain relevance to reported evidence | Initial task keeps surroundings conditional; follow-up reflects only reported details and preserves uncertainty |
| Suitability | Ignores constraints/focus, introduces a hazard, or offers an impractical task | Fits selections but is vague, overloaded or poorly suited to the supplied conditions | One concrete, achievable, conditional activity within the selections, with room to skip |
| Screen-light experience | Requires camera, navigation, ongoing instructions or device interaction outdoors | Needlessly complicated or hard to remember without checking | Read once, pocket the phone, remember one simple observation |
| Adaptation (follow-ups only) | Ignores feedback or repeats the prior activity | Minor wording changes, weak use of preferences/context | Meaningful activity change grounded in feedback/context while preserving the selected focus and other constraints |

Add a non-identifying reviewer label, a brief rationale and SHA-256 of the **exact UTF-8 raw reply**, including any whitespace, to each `review` object. Each dimension is an integer 0, 1 or 2; `adaptation` must be `null` for initial missions and scored for follow-ups. `onelap.evaluation.output_digest(text)` computes this hash. Leave `review: null` until a person has reviewed it. Fixtures in unit tests include fictional reviews solely to test report logic.

Missing or malformed replies cannot receive semantic reviews. Parsed but app-rejected replies can be reviewed, with the rejection still counted. Reports expose pending review counts, reviewed/eligible counts, mean score among reviewed replies, and counts fully meeting the rubric. A high mean over surviving replies is not success over the full set. In comparison, the full-mark rate uses all eligible cases as its denominator; missing/malformed replies contribute no full marks. A rubric score is human judgment, not model-certified grounding or a safety assessment.

## Matched comparison, not automatic promotion

Once the central base-model loop is verified, the dataset reviewed/expanded/frozen, and separately budgeted captures actually exist:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate.py prepare --split heldout --output .data\evaluation\heldout-manifest.json
.\.venv\Scripts\python.exe scripts\evaluate.py compare --baseline .data\evaluation\base-heldout.json --candidate .data\evaluation\adapter-heldout.json --output .data\evaluation\comparison.json
```

Comparison rejects fixtures, development/train runs, incomplete coverage, duplicate run IDs, unreviewed datasets, pending semantic reviews, missing adapter identity, changed datasets/methods/messages/inputs, different decoding, execution conditions or library versions. Genuine failed samples still belong in the comparison. If any measurements are missing, it shows coverage but withholds their mean delta. It reports each semantic dimension and mission/follow-up acceptance separately, not a declaration of a winner. Negative deltas are possible and are not hidden.

Model/capture/review identity, checkpoint and training-data hash are **self-attested metadata**. Hashes detect mismatches; they do not prove provider execution, absence of training leakage or dataset authenticity. Keep original capture/training provenance for inspection. No adapter has been trained or wired into the application yet. Report actual improvements only after real, reviewed matched runs; retain the better-validated model if tuning is ineffective. Promotion is always a separate human decision.

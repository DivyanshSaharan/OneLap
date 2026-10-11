# OneLap supervised corpus v1

This is **assistant-authored, agent-reviewed synthetic data**, not real outings or human-reviewed
evidence. It adds training targets; it does not train a model, sample Tinker, access Atlas, load
credentials or prove that an adaptation is useful outside.

## Frozen splits

The 30 scenario families were assigned to one split before their five variants were authored.
`datasets/onelap-sft-v1.json` contains:

| Split | Inputs | Families | Assistant targets | Workflows |
| --- | ---: | ---: | ---: | --- |
| Train | 100 | 20 | 100 | 20 initial missions, 80 follow-ups |
| Development | 20 | 4 | 0 | 5 initial missions, 15 follow-ups |
| Held out | 30 | 6 | 0 | 5 initial missions, 25 follow-ups |

Development and held-out cases have no target completions. They are never returned by the
supervised-training helper. Development can guide a bounded experiment; do not inspect held-out
model outputs to revise prompts, targets or training settings. Keep failures in the denominator.
The separate 18-case seed input file remains untouched and unreviewed.

Training covers ordinary conditional observation, simpler within-focus tasks after difficult
feedback, meaningful alternatives after unwanted activities, useful-note development, uncertain
sound sources, unavailable visible patterns, quoted command rejection and selected-note priority.
All settings are generic. No real location, personal note, recording or GuardMate artifact is used.

## Offline checks and review

Run from the repository root:

```powershell
.venv/Scripts/python.exe scripts/validate_training_data.py
.venv/Scripts/python.exe -m pytest backend/tests/test_training_data.py
```

The loader is bounded, rejects duplicate JSON keys and unknown fields, validates every target
through the exact application mission/follow-up checks, checks family assignment, unique IDs,
five variants per family, split counts and target placement. Normalized full-input duplicates and
source-observation reuse across families are rejected even when punctuation, whitespace or case
changes. These guards cannot prove the absence of all semantic similarity.

`datasets/onelap-sft-v1.manifest.json` freezes canonical corpus, exact application input and training
message/target hashes. Changing the data or the application prompts invalidates validation until
the manifest is explicitly reviewed and re-frozen; never silently update it during a run.

The authoring agent reviewed conditional wording, factual reflection, unchanged selections,
within-focus adaptation, phone-free instructions and policy/schema validity. The label stays
`agent_reviewed`. The existing evaluation projection deliberately remains `unreviewed`, because
that older schema's approved semantic-review status means **human** review. Do not convert agent
scores or checklists into human reviews. Application acceptance, semantic review and outdoor
usefulness remain separate measurements.

Before spending on training, an independent agent or the maintainer should inspect the 100 targets
for unsupported claims, poor adaptations, repetition and misleading encouragement, then record
that review with these hashes. A later human review may improve the corpus, but must be explicitly
recorded rather than inferred from approval to implement.

## Integration API

`onelap.training_data` exposes `load_corpus`, `evaluation_dataset`, `supervised_examples`,
`target_text`, `frozen_manifest` and `verify_frozen_corpus`. Hosted workflows must call
`verify_frozen_corpus()` using the committed default corpus/manifest before creating a client
or reserving spend; it returns the corpus only when all frozen hashes match. Alternate file
arguments are for offline review, not for silently re-freezing a paid experiment. Errors are
fixed codes and never echo invalid corpus payloads. Each supervised example holds its exact `EvaluationCase`
under `.case` and a typed `.assistant_target`. Use the existing `messages_for(example.case)` to
build prompts, append only `target_text(example)` for training and use the same tokenizer/chat
template with thinking disabled. Never construct a cheaper different training prompt or train on
development/held-out inputs.

## Limitations

This is a small, patterned pilot: five variants per family share an activity pattern, and the 150
inputs are not 150 independent real-world experiences. Only 20 initial missions are in training;
the evaluation's ten initial-mission cases are narrower than the whole application selection
space. All fictional follow-ups are completed outings because the reused seed schema does not
represent stopped/skipped outcomes. Those gaps must not be described as tested coverage.

No held-out gold wording is provided. Exact wording agreement is not quality. A future comparison
must identify the real base model and adapter, keep decoding/memory/prompts identical, record every
failure, distinguish deterministic checks from human semantics, and avoid claiming improvement
without evidence. Training and model capture are separate, capped operations; this command is
strictly no-spend.

# Increment 6: repeatable integration verification

## What it checks

`scripts/smoke.py` runs a configuration preflight by default. It reads only local configuration and the existing spend ledger, reports missing dependencies/credentials and approval gates, and checks that there is enough allowance for two worst-case model reservations. It does not contact Tinker or Atlas during preflight, print credential values, or change `.env`.

With `--live` and an enabled configuration, it exercises the actual FastAPI routes in-process with the real Tinker provider and Atlas adapter:

1. Generate a 15-minute courtyard/evening/texture mission using base Qwen.
2. Store a clearly labelled fictional observation under a fresh random test journal owner.
3. Upload the same entry again and verify that exact readback contains only one entry.
4. Check that a request for a different owner is rejected.
5. Retrieve the test record through the follow-up route and generate a reflection/next mission.
6. Delete the test entry, verify that it no longer appears, and confirm that replay cannot restore it.

The fictional observation says that rough and smooth surfaces were noticed and that a gentler next task is preferred. This does not represent a real outing. The existing personal journal is never loaded or deleted. Deletion leaves a content-free tombstone in Atlas; if cleanup fails, the report marks the run failed and includes the test IDs for investigation. Cleanup is also attempted if a stored upload loses its reply.

## Running it

Run from the OneLap root after installing the development, journal and AI requirements:

```powershell
.\.venv\Scripts\python.exe scripts\smoke.py
```

Preflight prints JSON. Exit 0 means ready, exit 2 means configuration blocks the live test. A ready preflight is not a remote connection check.

Once live testing and its data/spend boundary have been approved, use the existing server configuration to enable hosted requests, data/reflection sharing and Atlas sync, set the approved budget/request allowance, then run:

```powershell
.\.venv\Scripts\python.exe scripts\smoke.py --live
```

The runner does not override the server gates. It uses the existing `.data/inference-budget.json` reservations instead of creating a new budget on every run, makes at most one mission and one follow-up request, and does not automatically retry a model failure. Reports are written to ignored `.data/smoke/<uuid>.json`; each contains labelled synthetic inputs, validated results if available, stage timings, cleanup status, model/prompt identity and the change in estimated spend reservations. Bounded raw synthetic-test replies are captured before parsing, including rejected outputs; credential values and raw provider/database exceptions are omitted. This capture is scoped to the fixed fictional workflow, not ordinary personal requests. Reports are not automatically published.

If a valid mission was captured but a later stage failed, a separately approved follow-up-only run can reuse that report:

```powershell
.\.venv\Scripts\python.exe scripts\smoke.py --resume .data\smoke\<previous-report>.json
.\.venv\Scripts\python.exe scripts\smoke.py --live --resume .data\smoke\<previous-report>.json
```

The first command is still a read-only preflight. Resume checks the exact synthetic inputs, validates the mission and verifies that its original captured reply matches. It records the source report's SHA-256, needs allowance for one model request, and creates a fresh test journal. Editing a report is not a way to substitute personal notes or a handwritten mission. Resuming does not grant permission for another request.

The API client is an in-process ASGI client, not a network/browser test. A successful run proves the checked API workflow on that configuration; it does not prove phone usability, offline behavior, outdoor usefulness or model accuracy. Every report keeps semantic review marked pending until a person reviews it.

## Verification

282 offline backend tests pass, including 13 smoke-runner tests covering readiness, insufficient/corrupt budgets, full API flow, invalid model output, failed initial generation, lost upload replies, cleanup failure, personal-journal isolation, response capture, validated resumption and disabled-gate behavior. Five follow-up regression cases cover the selected schema constants and rejection of the focus drift observed live. The 126 frontend tests include compatibility with both follow-up prompt versions. Four production-browser checks pass with installed Edge using labelled fixtures, including offline reload, responsive layout, disabled-provider behavior and journal synchronization/deletion. TypeScript, production build, Prettier and Ruff lint/format checks pass. Tinker/tokenizer dependencies were installed and their imports plus `pip check` pass.

Windows sandbox restrictions initially prevented Vitest from reading temporary transformed modules and Edge from launching. The unit suite passed with a repository-local temporary directory; the browser suite passed outside the sandbox with a disposable profile. The failed preview process was stopped after verifying its exact command. No browser test contacted Tinker or Atlas, and no source change was needed for these environment failures.

## Live outcome and prompt correction

After the first rejected mission, the user approved two additional requests. Both additional requests were used, for three samples in total. Further hosted testing waits for fresh approval. Their total estimated reservation was $0.002278 under the agreed $0.05 cap; this is not measured billing.

One mission passed application validation. The first Atlas attempt failed due to sandbox SRV DNS resolution; a read-only check outside the sandbox verified the attempted entry was absent. Reusing the captured mission avoided another mission sample. The resumed run passed real Atlas storage, identical-upload idempotency, exact readback, owner rejection, deletion and replay rejection. It reached Qwen for the follow-up, but the output changed `textures` to `light` and was correctly rejected. Test observation content was removed; a content-free tombstone remains. The personal journal was untouched.

The revised `follow-up-v2` prompt supplies exact constant values for minutes, setting, conditions and focus, explicitly asks for a gentler task within that focus, and discourages copying the previous activity. This schema is supplied in the prompt, not enforced by a constrained decoder. Application validation is unchanged; it still rejects focus drift. The frontend accepts saved `follow-up-v1` cards as well as new `follow-up-v2` cards. The revision is locally tested but has not been live-tested; no accepted live follow-up or successful complete live loop is claimed.

Saved `.env` gates stayed off throughout; only approved subprocesses enabled them. Further hosted tests need new approval. See [the reviewed evidence summary](live-smoke-2026-10-10.md) for timings and limitations.

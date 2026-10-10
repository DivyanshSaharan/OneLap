# Production-browser integration check

This harness runs the built frontend and real FastAPI routes over loopback HTTP, using a new disposable browser profile. It tests mission generation/saving, browser-offline reload, local fictional observation persistence, explicit sync/readback, reviewed follow-up generation/acceptance, explicit deletion and offline follow-up reload. It does not operate your existing browser, phone or personal journal.

## No-spend verification

```powershell
npm.cmd run build
$env:ONELAP_TEST_BROWSER = 'msedge'
.\.venv\Scripts\python.exe scripts\browser-smoke.py --fixture
```

Requires installed Edge, Python development/journal/AI dependencies and the existing frontend dependencies. Omit the Edge setting if Playwright Chromium is already installed in the project's ignored `.data/playwright-browsers` cache. The runner does not install a browser automatically.

Fixture mode does **not read `.env`**, create Tinker/Atlas clients or change the real spending ledger. It uses explicitly labelled fixture outputs and an in-memory journal behind real application routes, not intercepted API responses. Fixture token reservations live inside that run's ignored directory and are not real model requests. Fixture results cannot establish model quality, real Atlas behavior or category eligibility.

Port 8770 must be free. The runner owns an exclusively bound `127.0.0.1:8770` socket; if another API is running there, it fails without attaching to or terminating that process. The static Wi-Fi/USB preview on port 4176 is separate and unchanged. Never expose/tunnel the test backend.

## Read-only preflight

```powershell
.\.venv\Scripts\python.exe scripts\browser-smoke.py
```

Reports configuration, credential-presence booleans, existing estimated reservations and blockers. It does not start a server/browser, contact a provider or write a report. Exit 2 is expected while the saved sharing/spending gates are off. Readiness checks do not verify credentials, browser installation, a free server port or remote availability.

## Live run — fresh approval required

**One separately approved live run now passed on October 10**, using exactly two additional samples and verified isolated Atlas cleanup. See [the evidence and limitations](live-browser-2026-10-10.md). All six request allowances are now used. Before another run, separately approve up to two **additional** Tinker samples and the fictional Atlas entry, with a cumulative estimated-spend cap. An invalid reply/timeout consumes its allowance; there is no automatic generation retry or fallback.

The fixed input is 15 minutes / courtyard / daylight / textures. The only observation allowed is:

> Fictional browser-test observation, not a real outing: I noticed a rough surface beside a smooth one. Comparing both felt too difficult; next time I would prefer to notice only one texture.

The synthetic outcome is `completed` solely to exercise the follow-up gate; it is not a real completed outing. Feedback is `too_difficult`, with no earlier context. Mission selections go to hosted base Qwen through Tinker. That one mission snapshot, note and feedback are stored under a fresh random journal ID in Atlas; the selected fields go to Tinker for one follow-up. No personal records, location, audio or photographs are used.

Once explicitly approved, enable the existing gates only in a temporary child shell, leaving `.env` unchanged:

```powershell
# Run ONLY after approving these two requests and this data-sharing boundary.
$env:ONELAP_HOSTED_REQUESTS_ENABLED = 'true'
$env:ONELAP_DATA_SHARING_APPROVED = 'true'
$env:ONELAP_REFLECTION_SHARING_APPROVED = 'true'
$env:ONELAP_JOURNAL_ENABLED = 'true'
$env:ONELAP_ATLAS_SHARING_APPROVED = 'true'
$env:ONELAP_APPROVED_BUDGET_USD = '0.05'
$env:ONELAP_MAX_MODEL_REQUESTS = '<explicitly-approved-cumulative-request-limit>'
.\.venv\Scripts\python.exe scripts\browser-smoke.py --live --approve-synthetic-sharing
# Close this temporary shell after the run. Do not save these gates to .env.
```

`--live` and the sharing flag do not override disabled server gates. The runner sets a fresh, memory-only access token, uses the existing cumulative spend ledger and narrows the request ceiling to no more than two additional reservations (also respecting the configured maximum). Never reset/delete that ledger or increase the cap without approval. Estimated reservations are not a provider billing guarantee. Tracing is explicitly disabled by dependency injection, even if the parent environment contains Sentry settings; browser children receive only runtime paths, not credentials.

## Reports and cleanup

Unique ignored `.data/browser-smoke/run-*` directories hold timings, model identity, exact synthetic responses, bounded raw model replies, stage progress and screenshots. CLI output is limited to status, local report path, cleanup state and reservation count. Tokens/credential values and raw exception messages are never deliberately logged. Do not publish these artifacts without inspection and approval.

The browser is restricted to this origin and the expected public files/API operations. It allows only one mission and one follow-up attempt, one fictional upload and deletion of that same ID. The repository wrapper independently restricts writes/retrieval/deletion to the fresh owner and one exact fictional entry. Failed upload acknowledgments remain tracked.

Cleanup runs after browser success, error or timeout: delete the known test entry, verify no active entries remain in that fresh journal, and reject replay with the original entry. A content-free deletion tombstone remains in Atlas; provider backups may retain prior content. Cleanup failures force overall failure and require attention—do not call them successful deletion. The runner closes its browser and server on ordinary failure paths, but cannot guarantee cleanup after forcibly killing the process or power loss. Preserve the report/owner/entry IDs for targeted recovery; never mass-delete journals.

A passed fixture run proves the local harness and application plumbing. Only a separately approved passed live report can demonstrate the fresh hosted browser loop. Neither is a physical-phone test, an outdoor result, a semantic-quality score, a benchmark or fine-tuning evidence.

The latest fixture walkthrough also verifies that accepted follow-up source references survive deletion of the source note and offline reload. That local feature was added after the first live run; the earlier report does not include this additional check.

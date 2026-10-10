# OneLap

**After work, before scrolling.**

One short outdoor observation mission, then put the phone away. OneLap is being built around a long work-and-commute day, without publishing precise locations.

## Current state

The backend implements a Tinker adapter for open-weight Qwen3.5-4B, structured mission validation, protected API access and conservative spending reservations. The React interface supports preparation, explicit hosted-data consent, loading/error states, automatic local mission saving and a minimal pocket view. Hosted requests are disabled by default.

After returning, save a short observation and feedback locally, including while offline. The Atlas journal adapter supports explicit synchronization, stable-ID retries, owner isolation, pagination and deletion. Live checks with an isolated fictional entry passed for upload, duplicate prevention, exact readback, owner rejection, deletion and replay rejection. A real Qwen mission was accepted, but the live follow-up changed the selected focus and was rejected. **A successful accepted live follow-up remains unverified.**

Production builds cache the public app shell with a service worker and store one mission in IndexedDB. Offline reload is verified in a desktop browser at phone width, **not yet on a physical phone**. Installation prompts have not been verified.

Render deployment packaging is now included, but no Render service has been created or deployed. Optional metadata-only Sentry instrumentation is implemented and locally verified, with export disabled and no live dashboard test. An offline evaluation kit now prepares synthetic inputs and scores captured replies, but no hosted evaluation, training or outdoor test has happened. There is no public deployment or claim of measured model accuracy.

Automated model tests use explicit offline doubles; browser tests intercept private API requests with a clearly labelled fixture. The application has no fake-model fallback. Three separately approved hosted requests were made on October 10 using synthetic data: two mission attempts and one follow-up. The revised follow-up prompt is locally tested, not yet live-tested. See [the live-test evidence](docs/live-smoke-2026-10-10.md) for failures and limitations.

See [plan.md](plan.md) for the complete scope, schedule and approval rules.

## Local development

Requires Python 3.13. Commands below run from the OneLap project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-journal.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
```

Start the local API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn onelap.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8770 --workers 1 --no-proxy-headers
```

`GET /health` works without credentials. Local development needs no access token: API requests must come through loopback client/server addresses, approved localhost host/origin metadata and no forwarding headers. Keep this mode bound to `127.0.0.1`; do not expose or tunnel it. Setting an optional access token makes bearer authentication mandatory, with no local bypass. The service has no public Swagger/OpenAPI endpoints or cross-origin access enabled. This is a single-worker development service, not a production deployment.

The local environment is isolated from GuardMate. Nothing from GuardMate's private state or model adapters is reused.

## Render package (not activated)

The root `Dockerfile` builds the React PWA and FastAPI API into one same-origin service. `render.yaml` selects Render's free web-service plan, disables preview environments and automatic deploys, and configures model spending, Atlas access and reflection sharing off. It asks for only `ONELAP_ACCESS_TOKEN`, which must be entered as a Render secret and never committed. The bundled server refuses to start without that token. There is no Tinker or MongoDB credential in the template.

This is a single-person prototype, not multi-user authentication. The server token is shared by anyone you give it to, and all authorized clients address the same personal journal identity. Do not distribute the token or enable Atlas sharing for a public audience.

The AI and Atlas gates must remain off on the included free plan. Render free services have an ephemeral filesystem and can spin down after inactivity; OneLap's conservative spend ledger is file-backed, so it would reset when that filesystem is discarded. Free services also cannot attach a persistent disk. Before any hosted model use, the project needs a durable spend ledger and a separately approved configuration. The free service may take about a minute to wake after 15 minutes idle. See [Render's free-service limits](https://render.com/docs/free), [persistent-disk behavior](https://render.com/docs/disks), and [Blueprint secret configuration](https://render.com/docs/blueprint-spec).

No service, secret, or deployment has been created. This package alone is not evidence for the Best Use of Render category; that requires an actual deployment and a tested demo.

### Frontend

Use Node.js 22.12 or newer. Run these commands in another terminal from the project directory, keeping the API on port 8770:

```powershell
npm.cmd ci
npm.cmd run dev
```

The development interface is at `http://127.0.0.1:5174/`. Vite proxies `/api` to the loopback API; no API key belongs in the frontend. Open **Backend connection → Connect to local backend** to check status, without entering a token. The optional protected-server form is for a server explicitly configured with a token. The hosted-selection checkbox does not override server-side approval or budget gates.

To verify the production/offline build:

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run format:check
npm.cmd run build
npm.cmd run preview
```

Production preview: `http://127.0.0.1:4174/`. Service-worker caching is intentionally disabled in the development build. A phone opening a laptop's ordinary LAN HTTP address is not a secure service-worker context; use a suitable HTTPS setup when testing on an actual phone. Do not expose the private API publicly just to test it.

The automated browser suite starts its own production preview on port 4175. Build first. With an existing Microsoft Edge installation:

```powershell
$env:ONELAP_TEST_BROWSER = 'msedge'
npm.cmd run test:e2e
```

Alternatively install Playwright's Chromium (`npx.cmd playwright install chromium`) and leave `ONELAP_TEST_BROWSER` unset. These tests use disposable browser contexts and fictional API responses, not Tinker or Atlas. They do not measure mission quality.

### Saved missions and offline limitations

- A successful generation replaces the one saved mission on this browser/device. Saved observations retain their own mission snapshots.
- Read the mission, then use **I'm heading out** for the minimal view. It starts no timer, tracking, model request or completion record.
- The access token stays in memory and is forgotten on reload. It is not written to IndexedDB, local/session storage, URLs or service-worker caches.
- Saved mission text is not encrypted or hidden behind an account on the device. On a shared device, use **Clear this device's saved mission**; **Forget access** alone does not remove it.
- A storage failure preserves the visible mission but does not claim it can reopen offline. If replacement saving fails, an older mission may remain on disk; try saving again before leaving.
- Offline reading requires both the downloaded app shell and saved mission. Browser eviction, private mode or clearing site data can remove them; this is not guaranteed permanent storage.
- Updates activate only after an explicit click, disabled during pending work or pocket mode. Generation is never automatically retried; after an error, reconnect/check server state before another attempt.

More implementation and test details: [docs/increment-2.md](docs/increment-2.md).

### Observation journal

- **I'm back — record an observation** opens the return form. Completion, stopping and skipping are self-reported; timestamps are device supplied, not tracked outing durations.
- **Save observation on this device** persists the note, feedback and mission snapshot in IndexedDB before any upload. Unsaved drafts do not survive a reload. A partially written draft remains linked to its original mission if another mission replaces the current one.
- Notes are not encrypted or protected by the access token on this device. Clearing the saved mission or forgetting access does not delete journal entries.
- Atlas status checks, cloud loading and synchronization are manual. Configuration status is not a database connectivity check. An explicit checkbox authorizes only the pending changes reviewed for that sync; there is no background upload or automatic retry.
- The first upload attempt permanently binds a local entry to that server's journal UUID. OneLap supplies a stable personal ID automatically; no owner setup is needed. An optional advanced owner override must remain stable, and an entry is not reassigned to another journal.
- Retrying a lost reply reuses the same ID and content. Different content under the same ID is rejected instead of overwriting it. Partial successes remain acknowledged; other changes stay pending.
- Confirmed removal erases local note content immediately and queues cloud deletion if the entry may have reached Atlas. Sync must confirm that deletion. Atlas retains a content-free ID/owner tombstone to block delayed uploads from restoring a deleted note; provider backups may retain earlier data.
- Cloud pages contain up to 20 records in stable-ID order, not newest-first order. Loaded cloud content stays in memory; the local outbox persists separately. Mission snapshots are **client-submitted**, not independently verified model results.
- Offline availability depends on browser storage and the installed app shell. Eviction, private mode and clearing site data can remove local notes. No background AI analysis occurs; optional follow-up is a separate, explicit action described below.

Setup: [docs/atlas-setup.md](docs/atlas-setup.md). Implementation and verification: [docs/increment-3.md](docs/increment-3.md).

### AI reflection and follow-up

This flow reached live Atlas and Qwen in the fictional integration test, but the response changed `textures` to `light` and was rejected. The revised `follow-up-v2` prompt gives the four selected constraints explicit constant values in its supplied schema and asks for adaptation within the chosen focus. This is prompt guidance, not constrained decoding; application validation still rejects mismatches. The revision has not been tested live. Saved `follow-up-v1` missions remain readable.

After explicitly loading the cloud journal, choose one completed observation with text and optionally up to two earlier completed notes. The page shows the exact outcome, feedback, observation and mission summary that the prompt will use. It shows the recording date for context, but dates and journal IDs are not included in the Qwen prompt. The browser sends selected IDs to the API; the server re-reads those exact, non-deleted records from the configured Atlas journal and verifies ownership before building one prompt.

No notes are analyzed in the background. Before a request, the user must check server readiness and approve that specific sharing request. The server also requires `ONELAP_REFLECTION_SHARING_APPROVED=true`, the existing hosted-request/data-sharing/spending gates, and the Atlas journal gates. The new sharing gate defaults to `false`; keep all gates off until the data and cost boundary is deliberately approved. One generation uses the existing estimated-spend reservation and request limit. Selected observation text, feedback and mission summaries are sent to hosted Qwen through Tinker; check the provider's current retention and terms before enabling it. The checkbox is a UI disclosure, not a stored or server-verifiable consent receipt; the server gate is global, so keep the API private and loopback-only.

The structured reflection and proposed mission are labelled model-generated. Application checks validate the mission schema, settings and restrictions, and reject an exact repeated instruction; these do not prove that the reflection is semantically grounded or that a mission is safe. Review the result before choosing **Use this next mission**. Acceptance saves the mission on this device; discarding it does not change the current mission. The response contains selected source IDs and the UI shows how many entries were used; those IDs are not yet persisted alongside the accepted mission. The successful Atlas checks do not establish follow-up quality or outdoor usefulness.

### Repeatable integration check

After installing the development, journal and AI requirements, run the read-only local preflight:

```powershell
.\.venv\Scripts\python.exe scripts\smoke.py
```

It reports configuration, dependency availability, credential presence and existing spend reservations, without contacting either provider or printing credential values. Exit 2 means live testing is blocked; with the default gates off, that is expected.

Only with separately approved data sharing and model spending, `--live` runs a fictional mission/journal/follow-up workflow using the real configured services. It uses a fresh test journal, never reads personal entries, reuses the existing spend ledger, performs no automatic model retries, and verifies cleanup even after a follow-up failure. Ignored local reports include bounded raw **synthetic-test** replies to diagnose rejected output; this is not production prompt logging. `--resume` can reuse a matching, previously captured mission to avoid another mission request. See [docs/increment-6.md](docs/increment-6.md) for commands and boundaries. All saved hosted/Atlas gates remain off after the approved test.

### Private diagnostic tracing

Optional Sentry spans distinguish selected-record retrieval, cold runtime setup, encoding, model sampling, estimated-spend admission and validation failures. Journal write/read/delete operations have separate timing spans. Only bounded counts, anonymous trace IDs, timestamps, fixed labels and known error codes pass the final payload allowlist—not observations, model text, record IDs, credentials or exception messages.

`ONELAP_TRACING_ENABLED=false` and `ONELAP_TRACE_SHARING_APPROVED=false` are the defaults; `ONELAP_SENTRY_DSN` alone does not enable export. Automatic integrations, logs, exception events, profiles, sessions and trace propagation are disabled. The real SDK's serialized envelopes were inspected using a local collector; no Sentry upload or dashboard result is claimed. Enabling tracing does not change AI/Atlas approval. See [setup](docs/tracing-setup.md) and [implementation/privacy tests](docs/increment-7.md).

## Configuration and approval

### Offline evaluation

The evaluation kit validates a synthetic family-split corpus, exports exact application prompts and replays captured replies through the same output checks. It separates application acceptance from human grounding, suitability, screen-light experience and feedback adaptation. Failures remain in denominators; missing measurements are not zero. Fixtures cannot support a model-comparison claim.

```powershell
.\.venv\Scripts\python.exe scripts\evaluate.py validate
.\.venv\Scripts\python.exe scripts\evaluate.py prepare --split dev --output .data\evaluation\dev-manifest.json
```

Both commands are offline: no `.env` reads, hosted SDK clients, data upload or credit use. Generated artifacts remain ignored and existing files are not overwritten. The 18 starter cases are assistant-authored and **unreviewed**, six each in train/dev/held-out families. They are not gold training completions, actual outings or accuracy evidence. A human-reviewed, frozen and expanded dataset plus separately approved genuine captures are needed before comparison. Training still waits for the complete base-model loop to work. See [commands and rubric](docs/evaluation.md) and [increment verification](docs/increment-8.md).

### Runtime configuration

Copy `.env.example` to the ignored `.env` file and edit it locally, without overwriting an existing file. Local use requires neither `ONELAP_OWNER_ID` nor `ONELAP_ACCESS_TOKEN`. For a future non-local deployment, use a random access token of at least 32 ASCII characters with no whitespace, never a fixture token. Never put API credentials or tokens in browser build-time environment variables, screenshots, commits or messages.

For now, keep these defaults:

```dotenv
ONELAP_HOSTED_REQUESTS_ENABLED=false
ONELAP_DATA_SHARING_APPROVED=false
ONELAP_REFLECTION_SHARING_APPROVED=false
ONELAP_APPROVED_BUDGET_USD=0
ONELAP_JOURNAL_ENABLED=false
ONELAP_ATLAS_SHARING_APPROVED=false
ONELAP_TRACING_ENABLED=false
ONELAP_TRACE_SHARING_APPROVED=false
```

Only after agreeing the hosted-data boundary and spending cap should the owner install `backend/requirements-ai.txt`, set `TINKER_API_KEY` privately, and explicitly enable all approval settings. Installing the AI dependencies may download software, but the service only creates the hosted sampling client during an enabled generation request. Health/status checks do not initialize it.

`ONELAP_MAX_MODEL_REQUESTS` adds a persistent request-count limit (default 20). Configuration is read when the service starts; restart after changes. Environment variables override `.env` values.

## API contract

| Endpoint | Access | Purpose |
| --- | --- | --- |
| `GET /health` | Public, loopback development | Basic process health only |
| `GET /api/model/status` | Local-only or configured bearer token | Actual model, approval state and reservation counters |
| `POST /api/missions` | Local-only or configured bearer token | Generate one validated mission |
| `GET /api/journal/status` | Local-only or configured bearer token | Journal configuration only; no database connection |
| `POST /api/journal/entries` | API access, server journal ID | Idempotently store one outing snapshot, observation and feedback |
| `GET /api/journal/entries` | API access, owner header | Load an owner-scoped page; optional `after` UUID |
| `DELETE /api/journal/entries/{id}` | API access, owner header | Replace a note with a content-free deletion tombstone |
| `GET /api/followups/status` | Local-only or configured bearer token | Check server gates; does not query Atlas or Tinker |
| `POST /api/followups` | API access, owner header | Re-read selected Atlas records and request one reflection/mission |

Optional protected mode: `Authorization: Bearer <private-access-token>`. Token-free mode only allows loopback development with local host/origin ports 4174, 5174 and 8770. Forwarded/proxied and cross-site requests are rejected. This is a convenience boundary, not authentication for other users on the same laptop.

This is one shared personal journal, **not multi-user authentication**. The stable journal ID is supplied automatically; an optional `ONELAP_OWNER_ID` override supports an existing journal. Journal reads/deletes require `X-OneLap-Journal-Owner`; uploads include `owner_id` in their envelope. The app obtains that ID from status and supplies it without manual entry. All must match the server. Journal operations are limited to 30 per minute, separately from generation.

The only accepted mission inputs are generic selections:

```json
{
  "minutes": 15,
  "setting": "courtyard",
  "conditions": "evening",
  "focus": "textures"
}
```

Minutes: `10`, `15`, `20`. Settings: `courtyard`, `park`, `familiar_walking_area`. Conditions: `daylight`, `evening`. Focus: `light`, `textures`, `sounds`, `general` (default). Extra fields, including location, photographs and instructions, are rejected.

The response contains a mission ID, title, brief instruction, reflection prompt, matching input constraints, an application-owned safety note and the actual base-model identity. A rejected or unavailable generation returns a stable error code, never a fabricated mission.

The API limits JSON bodies to 8 KiB, validates exact primitive types, rejects duplicate keys and allows at most six authenticated generation attempts per minute. Qwen input is bounded to 4,096 tokens and output to 512 tokens, with one sample, temperature 0.2 and thinking disabled.

## Validation is not a safety or grounding guarantee

The schema enforces short plain text, known setting values, no camera requirement and no phone use during the outing. Application checks reject changed constraints and conservative keyword matches for prohibited activities.

These checks can reject harmless wording and can miss paraphrases, unsupported environmental claims or unsuitable activities. They are not comprehensive semantic verification, species identification, route guidance or a safety assessment. Human-reviewed evaluation and outdoor testing remain required.

## Spending and failures

Before sampling, the service persists a reservation based on uncached input and maximum output token rates in `.data/inference-budget.json`. The initial rates are estimates from [Tinker's pricing](https://tinker-docs.thinkingmachines.ai/tinker/models/); recheck before live use. Reservations are never refunded, including invalid output or timeout, and are not actual invoice amounts or a guaranteed billing cap.

The ledger and request count survive service restarts. Atomic replacement and an exclusive reservation lease prevent overlapping ledger updates. A corrupt ledger or existing lease blocks admission instead of resetting counters. Do not delete the ledger to bypass a limit. An interrupted reservation may leave a lock; inspect it only with all OneLap processes stopped, preserving the ledger.

Provider failures/timeouts disable further generation until restart. A timeout does not prove the hosted job was cancelled; reservations remain. No automatic inference retry or fallback model is used.

The local ledger is operational bookkeeping, not the journal and not SQLite. Shared/multi-host budget admission must be redesigned before a distributed deployment.

## Data boundary

Current mission generation sends generic mission selections, instructions and schema to Tinker. It accepts no raw photos/audio, location or free-form journal entries. Explicit journal sync sends saved observation text, feedback, mission snapshots and device timestamps to Atlas. A separate follow-up request can send only the reviewed, selected observations, feedback and mission summaries to Tinker after per-request UI consent and the server-side reflection gate. The API receives IDs and fetches owner-scoped Atlas records; no history is automatically included. Do not include precise locations or private details in free-form notes.

Validation/provider errors do not return private inputs or SDK exception text. No Sentry exporter is enabled. `.env`, `.venv`, `.data`, caches and logs are ignored by Git.

## Verification

363 offline backend tests cover schemas, policy, access/errors, loopback and cross-site boundaries, admission, SDK parameters, timeouts, persistent/concurrent ledger updates, Atlas approval gates, owner isolation, idempotency, pagination and deletion races. They also cover deployment protection, selected-record ownership/order, prompt boundaries, follow-up constraints/repetition, route approval gates, later-context rejection, smoke cleanup/resumption and metadata-only tracing. The 26 tracing tests inspect actual SDK envelopes with an in-memory transport and forbid HTTP export. The 55 evaluation tests cover corpus separation, every-case scoring, failure denominators, exact prompt/output hashes, human-review applicability, fixture exclusions, comparison matching and offline-only CLI behavior. The last verified frontend suite remains 126 tests covering response validation, old/new prompt-version compatibility, optional credentials, token-free connection, local saving, IndexedDB migration, journal consent/ownership, failure recovery, concurrency, service-worker lifecycle/cache boundaries and follow-up selection/consent; frontend code is unchanged in increment 8.

Four automated browser checks passed using a production build and installed Edge: offline mission reload, layouts at 320/390/1280 pixels, blocked generation when the provider is disabled, and offline observation capture/reload followed by explicit synchronization, a lost-reply retry without duplication, and confirmed deletion. These use labelled fictional fixtures and offline cloud doubles. The real disabled API/proxy setup-error path was checked previously. Type checking, production build, Prettier and backend Ruff checks pass.

The unit/browser suites use offline doubles or labelled fixtures; they do not measure Qwen's mission/reflection quality. Separate real-service testing verified one accepted mission and the isolated Atlas checks, but not an accepted follow-up. The total local reservation was $0.002278 across three requests, not an invoice amount. This tiny smoke test is not an accuracy evaluation. Training comparison, physical-phone/installation checks and field results remain pending.

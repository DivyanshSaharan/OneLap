# OneLap

**After work, before scrolling.**

One short outdoor observation mission, then put the phone away. OneLap is being built around a long work-and-commute day, without publishing precise locations.

## Current state

The backend implements a Tinker adapter for open-weight Qwen3.5-4B, structured mission validation, protected API access and conservative spending reservations. The React interface supports preparation, explicit hosted-data consent, loading/error states, automatic local mission saving and a minimal pocket view. Hosted requests are disabled by default.

After returning, save a short observation and feedback locally, including while offline. The Atlas journal adapter supports explicit synchronization, stable-ID retries, owner isolation, pagination and deletion. An authenticated read-only Atlas ping passed; **journal operations have not been tested live yet**. Cloud operations and AI operations have separate approval gates, both off by default.

Production builds cache the public app shell with a service worker and store one mission in IndexedDB. Offline reload is verified in a desktop browser at phone width, **not yet on a physical phone**. Installation prompts have not been verified.

**Not yet implemented:** AI reflections or adaptation across outings, deployment, Sentry export, training or outdoor tests. There is no public deployment or claim of measured model accuracy.

Model tests use explicit offline doubles; browser tests intercept private API requests with a clearly labelled fixture. The application has no fake-model fallback. No live OneLap Tinker request has been made.

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
- Offline availability depends on browser storage and the installed app shell. Eviction, private mode and clearing site data can remove local notes. No AI analysis of observations occurs in this increment.

Setup: [docs/atlas-setup.md](docs/atlas-setup.md). Implementation and verification: [docs/increment-3.md](docs/increment-3.md).

## Configuration and approval

Copy `.env.example` to the ignored `.env` file and edit it locally, without overwriting an existing file. Local use requires neither `ONELAP_OWNER_ID` nor `ONELAP_ACCESS_TOKEN`. For a future non-local deployment, use a random access token of at least 32 ASCII characters with no whitespace, never a fixture token. Never put API credentials or tokens in browser build-time environment variables, screenshots, commits or messages.

For now, keep these defaults:

```dotenv
ONELAP_HOSTED_REQUESTS_ENABLED=false
ONELAP_DATA_SHARING_APPROVED=false
ONELAP_APPROVED_BUDGET_USD=0
ONELAP_JOURNAL_ENABLED=false
ONELAP_ATLAS_SHARING_APPROVED=false
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

Current mission generation sends generic mission selections, instructions and schema to Tinker. It accepts no raw photos/audio, location or free-form journal entries. Explicit journal sync sends saved observation text, feedback, mission snapshots and device timestamps to Atlas; it does **not** send them to Tinker. Do not include precise locations or private details in free-form notes. Future reflection/history sharing needs a separate consent boundary.

Validation/provider errors do not return private inputs or SDK exception text. No Sentry exporter is enabled. `.env`, `.venv`, `.data`, caches and logs are ignored by Git.

## Verification

253 offline backend tests cover schemas, policy, access/errors, loopback and cross-site boundaries, admission, SDK parameters, timeouts, persistent/concurrent ledger updates, Atlas approval gates, owner isolation, idempotency, pagination and deletion races. 121 frontend tests cover response validation, optional credentials, token-free connection, local saving, IndexedDB migration, journal consent/ownership, failure recovery, concurrency and service-worker lifecycle/cache boundaries.

Four automated browser checks passed using a production build and installed Edge: offline mission reload, layouts at 320/390/1280 pixels, blocked generation when the provider is disabled, and offline observation capture/reload followed by explicit synchronization, a lost-reply retry without duplication, and confirmed deletion. These use labelled fictional fixtures and offline cloud doubles. The real disabled API/proxy setup-error path was checked previously. Type checking, production build, Prettier, backend Ruff and dependency checks pass.

Passing these tests is not evidence that Qwen produces good missions or that live Atlas journal operations work. An authenticated Atlas ping passed separately; write/read/delete smoke testing, inference, training comparison, physical-phone/installation checks and field results remain pending.

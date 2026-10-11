# OneLap

**After work, before scrolling.**

One short outdoor observation mission, then put the phone away. OneLap is being built around a long work-and-commute day, without publishing precise locations.

## Current state

The backend implements a Tinker adapter for open-weight Qwen3.5-4B, structured mission validation, protected API access and conservative spending reservations. The React interface supports preparation, explicit hosted-data consent, loading/error states, automatic local mission saving and a minimal pocket view. Hosted requests are disabled by default.

After returning, save a short observation and feedback locally, including while offline. The Atlas journal adapter supports explicit synchronization, stable-ID retries, owner isolation, pagination and deletion. Live checks with isolated fictional entries passed for upload, duplicate prevention, exact readback, owner rejection, deletion and replay rejection. A separately approved production-browser run also passed the fresh mission → offline note → explicit Atlas sync → reviewed follow-up → deletion → offline reopening loop using real Tinker/Atlas. **This verifies the checked workflow, not semantic quality, physical-phone use or outdoor usefulness.**

Production builds cache the public app shell with a service worker. Google sign-in provides backend-verified identity and per-user Atlas access; IndexedDB separates missions and notes by that account's journal UUID. All app controls require verified sign-in. Local storage is **not encrypted**. The owner reports local Google login/logout works; automated account-switching checks use synthetic identities. A signed-in open tab works offline, but fresh offline reloads stay locked until online session verification. Physical-phone and outdoor evidence remain pending.

Render/Docker packaging is included, but no Render service has been created or deployed. Atlas-backed spending counters passed an isolated content-free live probe; the production counter is not migrated/activated. Google authentication is implemented following the owner's later approval; real login/session checks are pending, so paid public inference remains off. Optional metadata-only Sentry instrumentation is locally verified, with export disabled and no live dashboard test.

**One real Tinker LoRA pilot is complete.** With 100 synthetic supervised examples and one three-epoch Qwen3.5-4B candidate, held-out application acceptance improved from **20/30 (66.7%) to 29/30 (96.7%)**; development acceptance improved from 16/20 to 20/20. This is structured-output/application compliance, **not semantic accuracy or outdoor usefulness**. Human semantic review remains pending, and the app still defaults to the base model with hosted gates off. [Full results, failure and cost](docs/pilot-results.md) · [Public hash-bound metrics](reports/onelap-pilot-v1.json) · [Verified checkpoint selection](docs/checkpoint.md).

Automated model tests use explicit offline doubles; the standard browser suite uses labelled fictional responses, and the packaged-server fixture harness uses local service doubles. The application has no fake-model fallback. Six separately approved hosted samples were made on October 10 using synthetic data: three mission attempts and three follow-ups, with two accepted replies of each type. These are smoke samples, not an accuracy benchmark. See [the initial API evidence](docs/live-smoke-2026-10-10.md) and [the fresh live-browser evidence](docs/live-browser-2026-10-10.md), including semantic defects. A captured follow-up can be reviewed and imported locally without an API call, with an unverified-provenance label that persists offline. Nothing is imported automatically.

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

`GET /health` works without credentials. With `GOOGLE_CLIENT_ID` configured, protected APIs require a verified Google-derived session, including on localhost. Configure `GOOGLE_CLIENT_SECRET`, `MONGODB_URI` and exact `ONELAP_AUTH_ORIGINS` privately. Without Google configuration, development retains its loopback-only or optional bearer-token boundary; keep it bound to `127.0.0.1` and do not tunnel it. No public Swagger/OpenAPI endpoints or cross-origin API access are enabled. [Authentication setup and boundaries](docs/authentication.md).

The local environment is isolated from GuardMate. Nothing from GuardMate's private state or model adapters is reused.

## Render package (not activated)

The root `Dockerfile` builds the React PWA and FastAPI API into one same-origin service. `render.yaml` selects Render's free web-service plan, disables preview environments and automatic deploys, and keeps model spending, note synchronization and reflection sharing off. It requests private Google client configuration, the Atlas URI and the actual HTTPS origin; no credential values are committed. The bundled server requires Google configuration or an explicitly protected legacy token. The public deployment path uses Google authentication, not a distributed shared token.

Google sessions derive a separate journal UUID from each verified account. Atlas `auth_sessions` stores minimal revocable session metadata, separately from notes and global spending counters. Existing personal-journal data is not silently migrated. The legacy token-only development mode remains single-person; never distribute that token.

Model and note-sync gates remain off in the template. Render free services have an ephemeral filesystem, so production inference requires the new Atlas spending counter and an explicit immutable import of existing reservations; it refuses the file-backed mode for hosted production inference. [Migration setup](docs/budget.md) and [isolated Atlas evidence](docs/atlas-budget-verification.md) are provided. Real Google/Atlas-session verification must pass before public paid use. Free services cannot attach a persistent disk and may take about a minute to wake after 15 minutes idle. See [Render's free-service limits](https://render.com/docs/free), [persistent-disk behavior](https://render.com/docs/disks), and [Blueprint secret configuration](https://render.com/docs/blueprint-spec).

No service, secret, or deployment has been created. Docker is installed, but its Linux engine is not running; an actual image build remains unverified. The packaged UI/API is browser-tested locally, not container-tested. This package alone is not evidence for the Best Use of Render category; that requires an actual deployment and a tested demo.

### Frontend

Use Node.js 22.12 or newer. Run these commands in another terminal from the project directory, keeping the API on port 8770:

```powershell
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5174/` (development) or `http://localhost:4174/` (production preview), matching Google's approved browser origins. Vite proxies `/api` to the loopback API; no secret belongs in the frontend. Click **Sign in with Google**, then the official **Continue with Google** button. Verified sign-in is required for all app controls, including cached missions and imports; unavailable authentication stays locked. Sign-in never enables spending/sharing gates or uploads notes. The owner has confirmed local login/logout works. Keep the signed-in tab open offline: a fresh reload requires online session verification, and logout locks the workspace immediately even if revocation fails.

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

- A successful generation replaces the saved mission for the current journal on this browser/device. Saved observations retain their own mission snapshots. Disconnect selects a separate device-only slot rather than showing another journal's mission.
- Accepting a generated follow-up also saves its generating journal and ordered source-entry IDs locally. **How this was generated** shows them after reload without fetching notes or making model requests. References can outlive deleted notes; they do not restore content or prove grounding. Older saves remain readable without invented links, and imported files cannot supply these links.
- Read the mission, then use **I'm heading out** for the minimal view. It starts no timer, tracking, model request or completion record.
- The access token stays in memory and is forgotten on reload. It is not written to IndexedDB, local/session storage, URLs or service-worker caches.
- Saved mission text is hidden by the app's sign-in gate, but storage is not encrypted and remains accessible through browser tools. On a shared device, explicitly clear the account's mission/notes; sign-out does not remove them. Other journal slots remain until removed. [Device-isolation boundaries](docs/device-isolation.md).
- A storage failure preserves the visible mission but does not claim it can reopen offline. If replacement saving fails, an older mission may remain on disk; try saving again before leaving.
- Offline reading requires a previously verified signed-in tab kept open and a saved mission. Reopening requires online session verification. Browser eviction, private mode or clearing site data can remove saved content; this is not guaranteed permanent storage.
- Updates activate only after an explicit click, disabled during pending work or pocket mode. Generation is never automatically retried; after an error, reconnect/check server state before another attempt.

More implementation and test details: [docs/increment-2.md](docs/increment-2.md).

### Use a captured mission without another model request

Expand **Use a captured mission · no model request**, choose a single mission-response JSON, review all its text and metadata, check the local-save review box and save. The file stays on this device; importing does not enable generation, journal sync or tracing. A full smoke report is not accepted. The maximum file size is 16 KiB; duplicate keys, invalid schema/text, unsupported model targets and prohibited keywords are rejected. Validation is not a safety, authenticity or grounding guarantee.

Saving replaces the current mission only after local storage confirms success. Existing observation notes are kept. Imported files remain labelled **model provenance not verified**, including after offline reload and in pocket mode. Old saved missions remain readable. A later explicit cloud sync/follow-up has its own sharing boundary; imported snapshots are client-submitted, not independently verified model results.

[This unmodified captured example](examples/captured-followup-2026-10-10.json) came from the synthetic live retest, not an actual outing. Read [its provenance and quality caveats](examples/README.md) before deciding whether to use it. The app does not load it as a fallback. [Phone/outdoor instructions](docs/field-test.md) are provided; real field results remain pending.

### No-spend phone handoff and demo

```powershell
npm.cmd run build
npm.cmd run handoff
```

The private guide is `http://127.0.0.1:4176/handoff`. Unlike Vite preview, this static server has **no API proxy**: it serves only public build files and the captured example, rejects uploads/API routes, and never reads `.env`. [Android USB instructions](docs/phone-setup.md) explain loading through one local port, then unplugging and testing offline. No physical-phone or outdoor result is claimed yet. Keep the exact origin; local browser storage is not shared across ports/devices.

[The demo recorder](docs/demo.md) produces a locally reviewed video in a disposable desktop browser, showing captured base-model playback, pocket mode, disconnected reload and a fictional skipped outing note. It makes no cloud requests. Videos/screenshots/manifests stay ignored and local; public upload needs approval. [A DEV draft](docs/submission-draft.md) is prepared, but its video link and outdoor evidence are still pending. Nothing has been published.

### Observation journal

- **I'm back — record an observation** opens the return form. Completion, stopping and skipping are self-reported; timestamps are device supplied, not tracked outing durations.
- **Save observation on this device** persists the note, feedback and mission snapshot in IndexedDB before any upload. Unsaved drafts do not survive a reload. A partially written draft remains linked to its original mission if another mission replaces the current one.
- Notes are not encrypted or protected by the access token on this device. Clearing the saved mission or forgetting access does not delete journal entries.
- Atlas status checks, cloud loading and synchronization are manual. Configuration status is not a database connectivity check. An explicit checkbox authorizes only the pending changes reviewed for that sync; there is no background upload or automatic retry.
- The first upload attempt permanently binds a local entry to its journal UUID. Google mode supplies an account-derived ID verified by the backend. Legacy development retains its stable personal ID. Entries are not reassigned to another account or automatically migrated.
- Retrying a lost reply reuses the same ID and content. Different content under the same ID is rejected instead of overwriting it. Partial successes remain acknowledged; other changes stay pending.
- Confirmed removal erases local note content immediately and queues cloud deletion if the entry may have reached Atlas. Sync must confirm that deletion. Atlas retains a content-free ID/owner tombstone to block delayed uploads from restoring a deleted note; provider backups may retain earlier data.
- Cloud pages contain up to 20 records in stable-ID order, not newest-first order. Loaded cloud content stays in memory; the local outbox persists separately. Mission snapshots are **client-submitted**, not independently verified model results.
- Offline availability depends on browser storage and the installed app shell. Eviction, private mode and clearing site data can remove local notes. No background AI analysis occurs; optional follow-up is a separate, explicit action described below.

Setup: [docs/atlas-setup.md](docs/atlas-setup.md). Implementation and verification: [docs/increment-3.md](docs/increment-3.md).

### AI reflection and follow-up

The initial fictional integration test reached live Atlas and Qwen, but changed `textures` to `light` and was rejected. The revised `follow-up-v2` prompt gives the four selected constraints explicit constant values in its supplied schema and asks for adaptation within the chosen focus. A separately approved one-request retest now passed, using the captured mission and a fresh isolated fictional entry with verified cleanup. This is prompt guidance, not constrained decoding; application validation still rejects mismatches. The accepted text still assumes objects/night and has imperfect semantic focus. Saved `follow-up-v1` missions remain readable.

After explicitly loading the cloud journal, choose one completed observation with text and optionally up to two earlier completed notes. The page shows the exact outcome, feedback, observation and mission summary that the prompt will use. It shows the recording date for context, but dates and journal IDs are not included in the Qwen prompt. The browser sends selected IDs to the API; the server re-reads those exact, non-deleted records from the configured Atlas journal and verifies ownership before building one prompt.

No notes are analyzed in the background. Before a request, the user must check server readiness and approve that specific sharing request. The server also requires `ONELAP_REFLECTION_SHARING_APPROVED=true`, the existing hosted-request/data-sharing/spending gates, and the Atlas journal gates. The new sharing gate defaults to `false`; keep all gates off until the data and cost boundary is deliberately approved. One generation uses the existing estimated-spend reservation and request limit. Selected observation text, feedback and mission summaries are sent to hosted Qwen through Tinker; check the provider's current retention and terms before enabling it. The checkbox is a UI disclosure, not a stored or server-verifiable consent receipt; the server gate is global, so keep the API private and loopback-only.

The structured reflection and proposed mission are labelled model-generated. Application checks validate the mission schema, settings and restrictions, and reject an exact repeated instruction; these do not prove that the reflection is semantically grounded or that a mission is safe. Review the result before choosing **Use this next mission**. Acceptance saves the mission and its generating journal/selected source IDs in one local transaction; discarding it does not change the current mission. The metadata stores no copies of notes or reflections and is not added to uploaded mission snapshots. Offline details show the actual model target, prompt version and references without checking Atlas. Replacement failure preserves the old mission and references; generation/import clears stale links. See [increment 12](docs/increment-12.md). Successful Atlas checks do not establish follow-up quality or outdoor usefulness.

### Repeatable integration check

After installing the development, journal and AI requirements, run the read-only local preflight:

```powershell
.\.venv\Scripts\python.exe scripts\smoke.py
```

It reports configuration, dependency availability, credential presence and existing spend reservations, without contacting either provider or printing credential values. Exit 2 means live testing is blocked; with the default gates off, that is expected.

Only with separately approved data sharing and model spending, `--live` runs a fictional mission/journal/follow-up workflow using the real configured services. It uses a fresh test journal, never reads personal entries, reuses the existing spend ledger, performs no automatic model retries, and verifies cleanup even after a follow-up failure. Ignored local reports include bounded raw **synthetic-test** replies to diagnose rejected output; this is not production prompt logging. `--resume` can reuse a matching, previously captured mission to avoid another mission request. See [docs/increment-6.md](docs/increment-6.md) for commands and boundaries. All six approved samples have been used; future requests need fresh approval. All saved hosted/Atlas gates remain off after testing.

### Production-browser workflow check

```powershell
$env:ONELAP_TEST_BROWSER = 'msedge'
.\.venv\Scripts\python.exe scripts\browser-smoke.py --fixture
```

Unlike the earlier intercepted browser tests, this harness exercises the actual production UI and FastAPI routes over loopback HTTP. Fixture mode ignores `.env`, uses labelled local service doubles and isolates its ledger; it does not spend credits or access Atlas. The seven-stage loop passes: generated mission, offline mission/note persistence, consent-gated sync with exact readback, reviewed follow-up, deletion and offline next-mission reopening. It also exposed and fixed Windows registry MIME mappings that broke packaged JavaScript/service-worker loading.

Default mode is read-only preflight. One separately approved two-request live run passed on commit `f511d52`, using the production UI and real services with the fixed fictional note, no prior history, no fallback and verified test-note deletion/replay rejection. It preserved the existing ledger and saved configuration. [Evidence and limitations](docs/live-browser-2026-10-10.md) distinguish this from the subsequent local source-reference feature, which has fixture/unit coverage only. All approved requests are used; another live run requires new approval. See [commands, reports and limits](docs/browser-smoke.md). This is not phone, outdoor, quality or fine-tuning evidence.

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

Both commands are offline: no `.env` reads, hosted SDK clients, data upload or credit use. Generated artifacts remain ignored and existing files are not overwritten. The 18 starter cases are assistant-authored and **unreviewed**, six each in train/dev/held-out families. They are not gold training completions, actual outings or accuracy evidence. A human-reviewed, frozen and expanded dataset plus separately approved genuine captures are needed before comparison. The resumed base-model API loop passed, but training still requires reviewed data and a separate spending allowance. See [commands and rubric](docs/evaluation.md) and [increment verification](docs/increment-8.md).

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

With Google configured, the backend obtains journal ownership from the verified session; browser-supplied owner headers/envelopes are mismatch checks, never an authority. Journal reads, writes, deletion and selected follow-up retrieval are account-scoped. Without Google, legacy development retains one personal journal. Journal operations are limited to 30 per minute, separately from generation.

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

The response contains a mission ID, title, brief instruction, reflection prompt, matching input constraints, an application-owned safety note and the actual base/adapter identity. Adapter identities include receipt/training hashes, not the private checkpoint path. A rejected or unavailable generation returns a stable error code, never a fabricated mission.

The API limits JSON bodies to 8 KiB, validates exact primitive types, rejects duplicate keys and allows at most six authenticated generation attempts per minute. Qwen input is bounded to 4,096 tokens and output to 512 tokens, with one sample, temperature 0.2 and thinking disabled.

## Validation is not a safety or grounding guarantee

The schema enforces short plain text, known setting values, no camera requirement and no phone use during the outing. Application checks reject changed constraints and conservative keyword matches for prohibited activities.

These checks can reject harmless wording and can miss paraphrases, unsupported environmental claims or unsuitable activities. They are not comprehensive semantic verification, species identification, route guidance or a safety assessment. Human-reviewed evaluation and outdoor testing remain required.

## Spending and failures

Before sampling, the service persists a reservation based on uncached input and maximum output token rates in `.data/inference-budget.json`. The initial rates are estimates from [Tinker's pricing](https://tinker-docs.thinkingmachines.ai/tinker/models/); recheck before live use. Reservations are never refunded, including invalid output or timeout, and are not actual invoice amounts or a guaranteed billing cap.

The ledger and request count survive service restarts. Atomic replacement and an exclusive reservation lease prevent overlapping ledger updates. A corrupt ledger or existing lease blocks admission instead of resetting counters. Do not delete the ledger to bypass a limit. An interrupted reservation may leave a lock; inspect it only with all OneLap processes stopped, preserving the ledger.

Provider failures/timeouts disable further generation until restart. A timeout does not prove the hosted job was cancelled; reservations remain. No automatic inference retry or fallback model is used.

The local application ledger is operational bookkeeping, not the journal. Production mode uses a separate content-free Atlas collection with atomic admission and immutable import floors. The standalone training/evaluation pilot uses its own ignored SQLite reservation ledger; it does not replace the Atlas journal or reset application counters. The completed pilot reserved $0.285662 under its separate $0.75 token allowance; storage and invoice differences are documented in [the pilot results](docs/pilot-results.md).

## Data boundary

Current mission generation sends generic mission selections, instructions and schema to Tinker. It accepts no raw photos/audio, location or free-form journal entries. Explicit journal sync sends saved observation text, feedback, mission snapshots and device timestamps to Atlas. A separate follow-up request can send only the reviewed, selected observations, feedback and mission summaries to Tinker after per-request UI consent and the server-side reflection gate. The API receives IDs and fetches owner-scoped Atlas records; no history is automatically included. Do not include precise locations or private details in free-form notes.

Validation/provider errors do not return private inputs or SDK exception text. No Sentry exporter is enabled. `.env`, `.venv`, `.data`, caches and logs are ignored by Git.

## Verification

Latest October 11 checks: **524 backend tests, 229 frontend tests, seven Edge production-browser checks**, the seven-stage no-spend packaged-server workflow, 24 handoff and ten browser-boundary checks, Ruff lint/format, Prettier, TypeScript, production build and dependency checks. Authentication tests include locally signed RSA tokens and synthetic two-account isolation, not live Google/Atlas sessions. Sign-in and restored-account screenshots were inspected. Training completed 30 updates and all 100 admitted evaluation samples; frozen public metrics remain unchanged. No physical-phone outdoor result, container build, public deployment, live OAuth verification or Sentry dashboard evidence is implied.

Tests cover structured responses, API/consent boundaries, persistent admission, journal scoping/idempotency/deletion, offline storage, source provenance, hash-bound receipts, frozen training splits, capture accounting and public evidence privacy. Fixture/browser plumbing checks are deliberately separate from real model-performance evidence.

Implementation details and honest limitations: [device scoping](docs/device-isolation.md), [durable counters](docs/budget.md), [training](docs/training.md), [evaluation](docs/experiments.md), [pilot results](docs/pilot-results.md), [production UI](docs/production-ui.md) and [remaining deployment boundary](docs/predeployment-handoff.md). Older increment-specific test histories remain in `plan.md` and the individual increment documents.

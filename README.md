# OneLap

**After work, before scrolling.**

One short outdoor observation mission, then put the phone away. OneLap is being built around a long work-and-commute day, without publishing precise locations.

## Current state

The backend implements a Tinker adapter for open-weight Qwen3.5-4B, structured mission validation, protected API access and conservative spending reservations. The React interface now supports preparation, explicit hosted-data consent, loading/error states, automatic local mission saving and a minimal pocket view. Hosted requests are disabled by default.

Production builds cache the public app shell with a service worker and store one mission in IndexedDB. Offline reload is verified in a desktop browser at phone width, **not yet on a physical phone**. Installation prompts have not been verified.

**Not yet implemented:** journal, MongoDB Atlas integration, pending-observation sync, adaptation across outings, deployment, Sentry export, training or outdoor tests. There is no public deployment or claim of measured model accuracy.

Model tests use explicit offline doubles; browser tests intercept private API requests with a clearly labelled fixture. The application has no fake-model fallback. No live OneLap Tinker request has been made.

See [plan.md](plan.md) for the complete scope, schedule and approval rules.

## Local development

Requires Python 3.13. Commands below run from the OneLap project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
```

Start the local API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn onelap.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8770 --workers 1
```

`GET /health` works without credentials. The private endpoints require an access token. The service intentionally has no public Swagger/OpenAPI endpoints or cross-origin access enabled yet. This is a single-worker development service, not a production deployment.

The local environment is isolated from GuardMate. Nothing from GuardMate's private state or model adapters is reused.

### Frontend

Use Node.js 22.12 or newer. Run these commands in another terminal from the project directory, keeping the API on port 8770:

```powershell
npm.cmd ci
npm.cmd run dev
```

The development interface is at `http://127.0.0.1:5174/`. Vite proxies `/api` to the loopback API; no API key belongs in the frontend. Open **Private access** and enter your server's private access token to check status. The hosted-selection checkbox does not override server-side approval or budget gates.

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

Alternatively install Playwright's Chromium (`npx.cmd playwright install chromium`) and leave `ONELAP_TEST_BROWSER` unset. These tests use disposable browser contexts and fictional API responses, not Tinker. They do not measure mission quality.

### Saved missions and offline limitations

- A successful generation replaces the one saved mission on this browser/device. There is no journal/history yet.
- Read the mission, then use **I'm heading out** for the minimal view. It starts no timer, tracking, model request or completion record.
- The access token stays in memory and is forgotten on reload. It is not written to IndexedDB, local/session storage, URLs or service-worker caches.
- Saved mission text is not encrypted or hidden behind an account on the device. On a shared device, use **Clear this device's saved mission**; **Forget access** alone does not remove it.
- A storage failure preserves the visible mission but does not claim it can reopen offline. If replacement saving fails, an older mission may remain on disk; try saving again before leaving.
- Offline reading requires both the downloaded app shell and saved mission. Browser eviction, private mode or clearing site data can remove them; this is not guaranteed permanent storage.
- Updates activate only after an explicit click, disabled during pending work or pocket mode. Generation is never automatically retried; after an error, reconnect/check server state before another attempt.

More implementation and test details: [docs/increment-2.md](docs/increment-2.md).

## Configuration and approval

Copy `.env.example` to the ignored `.env` file and edit it locally. Generate a random access token of at least 32 ASCII characters with no whitespace; do not use a fixture token from the tests. Never put API credentials or access tokens in browser build-time environment variables, screenshots, commits or messages.

For now, keep these defaults:

```dotenv
ONELAP_HOSTED_REQUESTS_ENABLED=false
ONELAP_DATA_SHARING_APPROVED=false
ONELAP_APPROVED_BUDGET_USD=0
```

Only after agreeing the hosted-data boundary and spending cap should the owner install `backend/requirements-ai.txt`, set `TINKER_API_KEY` privately, and explicitly enable all approval settings. Installing the AI dependencies may download software, but the service only creates the hosted sampling client during an enabled generation request. Health/status checks do not initialize it.

`ONELAP_MAX_MODEL_REQUESTS` adds a persistent request-count limit (default 20). Configuration is read when the service starts; restart after changes. Environment variables override `.env` values.

## API contract

| Endpoint | Access | Purpose |
| --- | --- | --- |
| `GET /health` | Public, loopback development | Basic process health only |
| `GET /api/model/status` | Bearer token | Actual model, approval state and reservation counters |
| `POST /api/missions` | Bearer token | Generate one validated mission |

Authorization: `Authorization: Bearer <private-access-token>`.

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

The current generation sends generic mission selections, instructions and schema to Tinker. It accepts no raw photos/audio, location or free-form journal entries. The future Atlas journal and history-sharing boundary are documented in the plan, not implemented yet.

Validation/provider errors do not return private inputs or SDK exception text. No Sentry exporter is enabled. `.env`, `.venv`, `.data`, caches and logs are ignored by Git.

## Verification

200 offline backend tests cover schemas, policy, private access/errors, admission, SDK parameters, timeouts and persistent/concurrent ledger updates. 71 frontend tests cover runtime response validation, credentials, local saving, loading/errors, concurrency and service-worker lifecycle/cache boundaries.

Three automated browser checks passed using a production build and installed Edge: offline reload of a saved fixture without another API call, layouts at 320/390/1280 pixels, and blocked generation when the provider is disabled. The real API/proxy setup-error path was also checked in the browser with hosted requests forcibly disabled. Type checking, production build, Prettier and backend Ruff checks pass.

Passing these tests is not evidence that Qwen produces good missions. Live inference, training comparison, physical-phone/installation checks and field results remain pending.

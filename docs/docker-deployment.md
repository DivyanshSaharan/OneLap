# Docker and Render deployment

One image builds React and serves its public assets with FastAPI. There is no
Vite server, browser API key or second frontend service in production. The
runtime runs as a non-root user, uses one Uvicorn worker, handles termination via
`exec`, and probes `/health` without contacting Google, Atlas or Tinker.
The application user's primary group is `1000`, as required for reading Render's
runtime secret files. Do not switch the application to root to work around
secret-file permissions.

## Local container

Start Docker Desktop's Linux engine. Copy `.env.docker.example` to the ignored
`.env.docker`, then fill in Google credentials and the Atlas URI privately.
The local Compose setup deliberately ignores the root `.env` and overrides all
model, note-sync and tracing approval gates to off, regardless of the env file.

```powershell
Copy-Item .env.docker.example .env.docker
docker compose build
npm run test:docker
docker compose up -d
docker compose ps
docker compose logs --tail 50
docker compose down
```

Open `http://localhost:4178`. Add this exact origin to Google's Authorized
JavaScript origins for a manual login check. This port does not interfere with
the existing preview at 4174. Ports bind to loopback only; do not expose or tunnel
the Compose service. Signing in stores minimal Atlas auth metadata even with
journal sync off. No real login/model/upload test is implicit in a container build.

The image build does not need credentials. `.env`, `.data`, dependency caches,
test artifacts and private receipt files are excluded from the build context.
Do not run `docker compose config` without `--quiet`: expanded configuration may
print credentials. Do not share container environment dumps or unreviewed logs.
The local filesystem is disposable; no production spending ledger belongs there.

`npm run test:docker` uses the built `onelap:local` image, a disposable container
and fictional auth configuration with `--network none`. It verifies non-root
execution, public assets, absence of private state/import UI, signed-out session
configuration and rejection of anonymous/wrong-origin API access, then removes
only that container. No host port, private env file or credentials are used.
For configuration-only validation with the blank sample, set
`ONELAP_DOCKER_ENV_FILE=.env.docker.example` before `docker compose config --quiet`;
do not start that blank-credential Compose service or expect real login to work.

## Render first deploy: no model spend

1. Commit the reviewed deployment setup and connect this repository using its
   `render.yaml` Blueprint. Select Docker, keep automatic deployments off, and
   use `/health` as the health-check path.
2. Enter `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `MONGODB_URI` and
   `TINKER_API_KEY` only in Render's private environment configuration. Set
   `ONELAP_AUTH_ORIGINS` to the actual service's HTTPS origin, without a trailing
   slash/path. Add the same origin to Google's Authorized JavaScript origins.
   Our popup credential flow does not use an OAuth redirect URI.
3. The owner has now approved the trained adapter as the deployment target.
   Upload its exact private receipt as the secret file described below BEFORE
   the first startup; the Blueprint pins its path and SHA-256. Missing/mismatched
   receipts prevent startup rather than falling back to base. Keep every
   sharing/spending gate off and budget at zero during health, public assets,
   login/reload/logout and two-account checks. `GET /health` does not prove Atlas
   connectivity. Local diagnostic Compose remains base-only deliberately.
4. Before enabling inference, reread the existing local inference ledger and
   import both counters into the stable Atlas database/scope. Follow
   [budget migration](budget.md); never reset limits or choose a new scope to
   regain allowance. Training/evaluation reservations remain separate.

## Trained adapter configuration

The image already includes the frozen corpus manifest and method files needed
to verify the training receipt. The private receipt itself must not be committed
or copied into an image. Add a Render secret file named
`onelap-checkpoint-receipt.json`; that exact basename is excluded by
`.dockerignore` because Render also exposes secret files to Docker's build context.

Set these runtime variables together after reviewing the receipt and confirming
the saved sampler has not expired:

```text
ONELAP_MODEL_TARGET=adapter
ONELAP_CHECKPOINT_APPROVED=true
ONELAP_CHECKPOINT_RECEIPT=/etc/secrets/onelap-checkpoint-receipt.json
ONELAP_CHECKPOINT_RECEIPT_SHA256=<SHA-256 of the exact uploaded bytes>
```

Preserve the receipt's exact bytes: whitespace/newline changes alter its hash.
Test runtime read permissions for the secret file under the non-root user.
The smoke test now creates a root-owned, group-1000 `0440` fictional file inside
its network-disabled, capability-dropped container and checks that the non-root
application can read it but cannot read an owner-only `0400` control file.

Render's text editor can normalize Windows CRLF line endings to Unix LF. The
approved local pilot receipt has SHA-256
`eed06decf5bedd51684ae5065c434203605c372294284e0ae4f63a8f243829eb`;
the uploaded LF-only copy was verified to differ ONLY in line endings and has
SHA-256 `100313a3513de7e73adcdf47ef7c245dc13bb12e0e67a850be655707393e1467`.
Pin the hash of the exact verified file uploaded to your service. Do not replace
the expected hash with an arbitrary file's hash or disable validation to pass
startup. The same receipt/model/method bindings remain mandatory.
There is no automatic promotion, retraining or base fallback for a bad receipt.
The saved sampler has a seven-day TTL; no additional training/storage allowance
is implied. Checkpoint hash validation alone cannot prove remote availability.

Enable generation, reflection and journal sync only after separately approving
the respective gates and cumulative budget/request limits. Local Compose
intentionally cannot enable them through `.env.docker`; deployment activation
is a distinct reviewed step. Keep optional tracing disabled until approved.

## Release checks

- Image builds, health becomes healthy, static JS/CSS have correct content types.
- Google session configuration is available; anonymous protected requests return
  401, even if a caller supplies the legacy bearer token.
- Model/notes never run merely because the page loads or signs in.
- Real phone on mobile data: login, one approved mission, local observation,
  approved sync/follow-up, logout, and a second account's isolation.
- Open signed-in tabs can read offline; a fresh offline reload stays locked.
- Restart/redeploy retains Atlas sessions/notes/counters, not local files.

Render can build from the GitHub Dockerfile even when a local engine is unavailable.
Free services sleep after idle time and use an ephemeral filesystem; warm-up and
Atlas outages need honest error states, not synthetic mission fallbacks. See
[Render Docker](https://render.com/docs/docker),
[secret files](https://render.com/docs/configure-environment-variables), and
[free-service limitations](https://render.com/docs/free).

## Local verification — October 11

The installed Docker Desktop Linux engine was started and the multi-stage image
built successfully. The verified image is tagged `onelap:local` and
`onelap:deployment-check` locally (about 144 MB as reported by Docker). Compose
configuration passes with the blank sample, without printing credentials.

The network-disabled smoke test passed public assets/health, non-root execution,
signed-out session configuration, origin/anonymous/bearer-bypass rejection and
absence of the importer/private state. Its temporary container was removed.
The actual existing completed training receipt also passed non-root Linux loading
through a read-only secret-file-style mount with networking disabled. This checks
local integrity/read permissions, not Tinker sampler availability or Render's
secret-file permissions. `pip check` passes inside the image.

All 543 backend tests (including 19 new packaging contracts), formatting and the
Linux frontend typecheck/build pass. No Google login, Atlas connection, hosted
sampling, ledger migration, image-registry push or Render deployment was performed.
The existing root `.env` is unchanged; `.env.docker` was not populated and no local
Compose service was left running. Docker Desktop and the verified images remain
available for the next deployment step.

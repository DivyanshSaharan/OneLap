# Increment 5: protected Render package

## Scope

Bundle the phone-first React PWA and FastAPI backend into one same-origin Docker web service. Keep the package inert until the owner chooses to deploy it: no Render account operations, service creation, secret configuration, model requests, Atlas journal operations, or automatic deployment.

## Changes

- Added `ONELAP_SERVE_FRONTEND` to opt the API into serving a built frontend. A missing build fails startup instead of leaving a broken half-deployed service.
- Added an integration test for the SPA shell, static assets, no-store response headers, public health check and bearer-protected private API. Bundled deployment also refuses to start without the server token or a built UI.
- Added a multi-stage Docker build. It compiles the PWA, installs pinned backend dependencies, runs as a non-root user, and starts one Uvicorn worker.
- Added `.dockerignore` entries for credentials, local state, dependency trees and test artifacts.
- Added a Render Blueprint for one free web service, with previews and auto-deploys disabled. The only prompted secret is the server access token; hosted-model, Atlas and reflection gates are explicitly false, and the approved spend is zero.
- Documented that this is single-person shared-token access, not multi-user authentication, and that the free plan cannot safely run hosted inference while the spend ledger is file-backed.

## Safety and limitations

The Blueprint does not set `TINKER_API_KEY` or `MONGODB_URI`. Do not enable Qwen or Atlas on this free service: its filesystem is ephemeral, and the provider's local reservation ledger would be lost after restart or spin-down. A durable spend ledger is required before hosted model access can be considered. There is no Render service or secret configured, and no public browser-connectivity test has been performed.

The access token must be 32–256 ASCII characters without whitespace. It stays in the server environment and is entered into the UI only in memory. Anyone given this shared token can access the same personal journal identity if Atlas is later enabled; this is not a multi-user product.

## Verification

264 offline backend tests and 123 frontend tests pass. Ruff lint/format, Prettier, TypeScript and the production frontend build pass. The Render YAML parses and formats with Prettier. The three deployment tests cover same-origin static serving, private API authentication and fail-closed startup. A Docker client is installed, but no local Docker daemon is available, so the image itself could not be built here; the Render CLI is not installed. No live provider, database, Render account, service, or deployment is part of verification.

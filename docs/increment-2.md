# Increment 2 — a mission to read, then pocket

Implemented October 6, 2026. Commit and push approved by the user on October 6.

## Scope

A React/TypeScript interface for the existing private mission API: generic time/setting/conditions/focus choices, an explicit hosted-data checkbox, manual private status connection, visible pending/error states and one mission saved automatically in IndexedDB. Focus moves to a newly generated mission; saved missions appear before preparation controls, with a shorter header. Pocket mode removes preparation controls without implying completion.

Components separate private access, preparation, mission display, empty/loading content, header and notices. Hooks own API/mission state, connectivity and service-worker lifecycle. There is no polling, automatic model retry, background generation or fabricated app fallback.

Credentials are held only in React memory. Provider/API failures leave the previous mission intact and require a fresh private connection before generating again. Pending generation, local saving and clearing prevent conflicting actions. Storage failures do not claim successful persistence or deletion.

## Offline boundary

IndexedDB stores only a versioned mission response and saved timestamp, not an access token. A successful save replaces one current mission; it is not a journal. Save failure can leave a previous disk record. Local data is not account-protected or encrypted; clearing access and clearing a mission are distinct actions.

The production build emits a service worker containing an explicit app-shell asset list. Its cache version depends on bundle bytes, public icon/manifest bytes and worker logic. GET navigation uses the cached generic shell; known public assets use cached files. The public hashed-asset lookup ignores `Vary` because the preview server adds `Vary: Origin`, which otherwise breaks offline module/CSS loading. This exception applies only to the explicit public asset list. `/api/*`, `/health`, POSTs, other origins and unrelated assets are not intercepted or stored.

New worker activation is user-triggered, with no automatic reload during work. First installation is not labelled an update. Unsupported contexts, failed registration and readiness timeout report unavailable caching. Development builds do not register a worker. Browser eviction/clearing can still remove caches and IndexedDB.

No offline generation, observation entry, outbox, Atlas integration, journal, adaptation, deployment or diagnostics exporter is included.

## Verification

- 200 existing backend tests passed; Ruff lint/format remained clean.
- 71 frontend tests passed: runtime API parsing, credential placement, timeout/no-retry behavior, IndexedDB replace/delete/corruption handling, interface state/concurrency and worker/lifecycle boundaries.
- TypeScript, production build and Prettier checks passed.
- Three automated Edge browser tests passed against the built app on loopback: fixture generation/save and disconnected reload without another API request or retained credentials; layouts without horizontal overflow at 320, 390 and 1280 pixels; disabled-provider generation blocking.
- Browser tests label the synthetic response **E2E fixture — not model output**. Private routes are intercepted only inside disposable test contexts. Test fixtures are not included in the application bundle, and no Tinker request is made.
- The browser UI also connected through the Vite proxy to the actual FastAPI process and showed the expected private-access setup error. Hosted requests/data sharing were forcibly disabled, budget was zero and the access token unset for this smoke check. No inference ledger was created.
- The computer-use skill helped inspect the actual preview and its explicit update flow. A first-install update label and the public-asset `Vary` mismatch were corrected during verification.

These checks do not prove real Qwen mission quality, physical-phone behavior or installability. Phone disconnect/reload testing and outdoor use remain pending. No paid inference, training, deployment or account creation occurred during implementation. Repository publication was separately approved by the user.

## Handoff

Run commands are in README.md. Production preview and API may still be running on loopback; check the active terminal sessions before restarting. The smoke-test API intentionally has hosted generation disabled and private access unset. Stop/restart it using the owner's private OneLap configuration only after the relevant approvals. Do not copy GuardMate credentials.

Commit message: `feat: add offline-ready mission interface`.

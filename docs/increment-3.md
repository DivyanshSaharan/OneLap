# Increment 3 — outing journal and explicit sync

Implemented locally on October 6, 2026. Commit and push approved by the owner. A separately authorized read-only Atlas ping passed. No journal data was uploaded or sent to Tinker.

## Functional scope

The return flow records a self-reported outcome (`completed`, `stopped`, `skipped`), a short observation, optional feedback and the relevant mission snapshot. Completed outings require an observation; stopped/skipped outings may leave it blank. Saving works offline and creates a durable IndexedDB outbox entry. It is not an AI reflection or GPS completion check.

IndexedDB upgrades from version 1 to version 2 without discarding the saved mission. Unsaved form drafts remain in memory only; saved observations survive reload unless browser storage is cleared/evicted. A non-empty draft stays attached to its original mission if a new mission is generated.

## Synchronization contract

- Network operations happen only through explicit status, load or sync controls. Notes are never uploaded on mount, reconnect, focus or a timer.
- Sync consent captures the reviewed pending IDs. A new note added in another tab is not silently included in that approval.
- Before the first network write, the outbox atomically binds an entry to the server's stable owner UUID. This binding survives lost replies and prevents uploading it to another owner.
- Atlas inserts atomically under an owner/entry key. Matching-content retries are idempotent; conflicting content is rejected, not overwritten. Acknowledgment is validated before marking local sync complete.
- Successful items remain acknowledged if a later item fails. Failed items stay pending for a new, explicit attempt; neither the application nor driver automatically retries cloud operations.
- Removal needs confirmation. Never-attempted local notes can be erased locally. Possibly uploaded notes become content-free deletion markers; cloud deletion must be explicitly synced.
- Atlas deletion creates an idempotent content-free tombstone, including when deletion arrives before a delayed upload. It blocks subsequent uploads under that ID. IDs/owner metadata remain, and provider backups may retain prior content.

Local outbox operations are transactional and re-read current rows to handle concurrent tabs and late acknowledgments. Focus/manual refresh reloads local data but makes no cloud call. Corrupt/unavailable device storage blocks further writes/uploads until recovered; data is not silently discarded.

## Access and privacy

The user requested simplified local setup. A stable personal journal ID is now supplied automatically, with no manual UUID requirement. When no access token is configured, API access requires loopback client/server addresses, approved localhost host/origin ports and no forwarding/cross-site headers. Keep the server bound to loopback; do not expose or tunnel this mode. This does not authenticate other people on the same device.

An optional configured token restores mandatory constant-time bearer authentication with no local bypass. The protected-server form is tucked under an optional control. One server has one shared journal, not multi-user authentication. The requested journal ID must match server configuration. Tokens stay in React memory, not IndexedDB, URLs or service-worker caches. Journal responses are `no-store`, and validation/provider errors do not echo private text.

Atlas initialization is lazy, after separate sharing/enabled gates and valid owner/URI configuration. TLS verification, majority read/write concerns, primary reads and bounded driver timeouts are enforced. Operations have a separate 30/minute limit. Status reports configuration only and does not open a connection.

Cloud pagination returns 20 records per page in stable-ID order. The UI sorts loaded records by the client timestamp for display; timestamps are self-reported. Cloud-loaded content is memory-only. Stored mission snapshots are explicitly marked client-submitted, not trusted proof of model generation. Observations are plain text, not HTML, and have no precise-location field, but users must still avoid private details in free-form notes.

Local notes are not encrypted or hidden by the private token on a shared device. Forgetting access or clearing the current mission does not delete observations. Journal synchronization sends observation text, feedback, mission snapshots and timestamps to Atlas only. No journal context goes to Tinker in this increment.

## Verification

- 253 offline backend tests: approval/authentication gates, loopback/host/origin/proxy boundaries, schemas, secure configuration, owner isolation, duplicate/conflicting writes, concurrent retries, pagination, deletion-before-upload and replay protection, plus existing generation/budget tests.
- 121 frontend tests: token-free connection, optional credentials, storage migration, durable outbox, sticky ownership, concurrent bind/remove, late acknowledgments, corrupt storage, explicit consent, drafts, failure recovery and existing mission/service-worker tests.
- 4 production-browser checks in Edge: offline mission reload; responsive layouts; disabled-model gate; offline observation capture/reload, explicit sync, a simulated lost reply retried without duplication, and confirmed deletion.
- Type checking, production build, Prettier, Ruff and Python dependency checks passed.

Database unit tests use offline collection/client doubles. Browser tests use explicitly labelled fictional responses and observations in disposable contexts. These are not live Atlas tests, model-quality evaluation, physical-phone evidence or outdoor results.

## Next boundary

The owner needs [Atlas setup instructions](atlas-setup.md), private configuration and separate authorization for a fictional live write/read/delete smoke test. Credentials alone do not approve uploading data. Physical-phone/offline checks remain pending. Grounded reflection/adaptation will be a later increment with its own hosted-data boundary. No deployment, telemetry or training is enabled.

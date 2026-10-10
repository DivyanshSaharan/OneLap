# Increment 9: captured-mission handoff

Committed and pushed as `0047c60` on October 10, 2026 with approval. Increment 8 was committed and pushed as `953a4bf` earlier that day. The verification below describes increment 9's boundary; later additions are documented separately.

## One functionality

A local, review-before-save mission import makes a captured result usable in the actual app without another paid generation. A bounded single mission-response JSON is checked for schema, duplicate keys (including escaped keys), known model identity and conservative prohibited keywords. Full reports, unsupported targets, invalid text and oversized files are rejected without echoing content. These are shape/heuristic checks, not verified model provenance or semantic safety.

The file is previewed on-device and is not uploaded. Save requires an explicit review checkbox, respects pending-work locks, and changes the active mission only after IndexedDB confirms storage. Discard, parse/read failure or save failure leaves the current mission intact. Saving replaces only the current mission, not existing journal notes. Imported provenance is retained across offline reloads and shown in both normal and pocket modes. Older saved records remain readable; new ordinary API/follow-up results replace the import label appropriately. Credentials and sharing gates are untouched.

The included example is an unmodified, locally cross-checked mission from the successful synthetic follow-up. It is not automatically displayed, a new request or an actual outing. [examples/README.md](../examples/README.md) documents provenance and quality problems. [field-test.md](field-test.md) supplies an unfilled phone/outdoor checklist and truthful demo procedure.

## Separately approved live verification

The user approved exactly one additional synthetic follow-up, reusing the previous validated mission under the existing $0.05 cumulative cap. The resumed real Tinker/Atlas API workflow passed: upload, duplicate upload, exact readback, other-owner rejection, accepted `follow-up-v2`, deletion/empty readback and replay rejection. No new mission was sampled; no personal entries were read. The test note was deleted and a content-free tombstone remains.

This used one request with an estimated $0.000825 reservation, bringing the preserved ledger to four samples/$0.003103. This is not actual billing or credit balance. The follow-up API stage took about 14.75 seconds, including runtime setup and retrieval, not isolated inference. Saved gates are still off; tracing was disabled and no further requests or training were performed. The single additional allowance is now exhausted.

The payload preserves all four selected fields and avoids an exact repeat. Its meaning is still imperfect: night/objects are assumed, the task leans on shadows, and a proposed choice is phrased as already made. Formal human review remains pending. Resumed API success is not a fresh two-generation run, browser-to-live-backend test, training comparison, model-accuracy claim or outdoor evidence. See [the updated evidence](live-smoke-2026-10-10.md).

## Verification

155 frontend tests pass (29 new cases), with TypeScript, production build and Prettier checks. Five production Edge checks pass, including offline local import/reload, review gating, persistent unverified labels, rejected-file handling, 320/390/1280-pixel layout checks and zero private API requests for import. Browser fixtures are explicitly labelled, not real Qwen results. The 363 backend tests and Ruff/dependency checks also pass. Physical-phone, installation, real outings, demo recording, training and public deployment remain pending.

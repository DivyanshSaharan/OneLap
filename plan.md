# OneLap: implementation and handoff plan

Updated: October 10, 2026. Status: increments 1–10 are implemented and pushed; latest commit `07f19e2` adds the API-free phone/demo kit and DEV draft. Increment 11 implements a repeatable production-browser workflow and fixes Windows packaged-file MIME types; it is uncommitted. Its full loop passes with labelled local services, not new hosted requests. The user plans a phone/outdoor check tomorrow; no result is claimed yet. A separately approved fourth synthetic request accepted `follow-up-v2`; the resumed real Tinker/Atlas API workflow and verified cleanup passed. The result still has semantic weaknesses and is not a fresh two-generation, live browser/phone, accuracy or field test. Estimated reservations total $0.003103 across four samples, not measured billing; all request allowances are used. Saved AI/Atlas/tracing gates remain off. No hosted evaluation or training, Render service or Sentry project has been created.

## Product

**OneLap — After work, before scrolling.**

A personal AI that creates one achievable outdoor observation mission, learns from what the user noticed, and adapts the next outing. The motivating story is a work-and-commute routine running from 7 AM to 7 PM. Success means a useful outing with little screen interaction, not engagement, streaks or distance.

Privacy instruction: never include the user's real city, neighbourhood, address, office or identifiable outdoor location in documentation, datasets, demo assets or the submission. Use generic settings such as a courtyard, park or familiar walking area.

New project, separate from GuardMate:

`D:\sp2-20240124T210502Z-001\sp2\HactoberFest\OneLap`

Challenge: [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

## First-release loop

1. Choose 10, 15 or 20 minutes, a generic familiar setting, user-supplied daylight/evening conditions and activity preferences.
2. Receive one compact, achievable observation mission, not a list of choices or an ongoing chat.
3. Save it on the phone and pocket the phone during the outing.
4. Return with a short written observation and feedback.
5. Get a concise reflection grounded in that observation and an adapted next mission.

The first outing works without prior history or a photograph. Users can skip, stop, or report an unsuitable mission. No GPS, navigation or compulsory photography. Avoid invented landmarks, unsupported species identification, approaching strangers, entering private property, handling unknown objects or unnecessary hazards. The system does not determine that a location, weather condition or activity is safe.

## Architecture

| Component | Decision |
| --- | --- |
| Phone-friendly UI | React, TypeScript, Vite |
| Offline mission and pending observations | PWA, service worker, IndexedDB |
| Backend/schema validation | FastAPI, Pydantic |
| AI planning, reflection and adaptation | Qwen/Qwen3.5-4B through Tinker |
| Persistent journal and agent memory | MongoDB Atlas |
| Hosting | Single-origin Render Docker web service for frontend and lightweight API; deployment remains opt-in |
| Diagnostics | Sentry Agent Tracing, private content capture disabled |
| Tests | Pytest, Vitest, real browser/phone checks |

The hosted backend calls Tinker directly. No local inference worker, public Ollama endpoint or laptop-to-cloud tunnel is needed. Atlas replaces SQLite for persistent data; IndexedDB is the phone's cache/outbox, not a second authoritative database.

Generation and synchronization require connectivity. Reading a downloaded mission and recording a pending observation should work offline. Verify this on an actual phone after disconnecting. Do not claim that the whole product is offline.

## Model requests and application checks

Use the Tinker Python SDK sampling pattern already proven in GuardMate, with fresh OneLap prompts, schemas and tests. Credentials remain server-side. Do not copy GuardMate's secrets, database, recordings, delivery dataset, spending ledger or trained checkpoint.

Request workflow:

1. Authenticate, validate inputs, enforce request limits and admit estimated spend.
2. Retrieve owner-scoped preferences, recent missions, observations and feedback from Atlas.
3. Build instructions, structured output schema and clearly delimited context/history data.
4. Apply Qwen's tokenizer/chat template, initially with thinking disabled; sample through Tinker.
5. Parse and validate output before presenting or saving an accepted result.
6. Record relevant provenance references and actual model/checkpoint identity.

Use bounded input/output sizes, one sample and no unbounded retries. Keep synchronous SDK work off the async event loop and reuse the client/tokenizer where appropriate. Explicitly handle malformed output, timeout, budget refusal and provider failure. Never present fixtures or handwritten fallbacks as live model output.

The model interprets observations and generates adaptations. Application code owns restrictions, validation, state transitions, access control and persistence. Source references make grounding inspectable but do not prove semantic correctness. Self-reported model confidence is not an accuracy measure.

## Memory and offline synchronization

Records: preferences, missions, outings/observations, feedback and model-run metadata. Keep user observations distinct from model interpretations. Link follow-up missions to the observations used. Ordinary recent-history queries are sufficient initially; no vector database/search requirement.

Scope every read/write to the server's journal ID. Current local mode has one shared personal journal with an automatic stable ID, not authenticated individual users. Use stable IDs and idempotent synchronization to prevent duplicates. Pending observations must survive reloads, show sync status and not silently overwrite newer data. Completion is user-reported; opening a mission is not completion.

## Privacy, security and cost boundaries

- No precise-location field or GPS permission.
- Explicit journal sync stores observation text, feedback and mission snapshots in Atlas. No background journal reads or model analysis occur. A user-selected follow-up can send the reviewed observation, feedback and mission summary to Tinker only after per-request UI consent, a separate server sharing gate and the existing provider, budget and Atlas gates.
- No raw photographs, microphone input or vision processing in the first release.
- Sentry receives allowlisted timings, model identity and failure codes, not prompts, outputs, journals, credentials or location. Verify SDK defaults and exported events before enabling telemetry.
- Provide journal deletion and relevant local cache/outbox clearing. Explain provider retention/backups; do not promise immediate deletion everywhere.
- Protected private access for personal data. Public demo content is separately reviewed and labelled. No unrestricted public paid-inference endpoint.
- Server-side secrets, strict allowed origins, least-privilege Atlas access, bounded payloads and request/concurrency limits.
- Agree a total inference/training/evaluation spending cap before any paid experiment; check remaining credits. Prior cost estimates are not the current billing balance.
- Token reservations are estimates, not a guaranteed provider billing cap. Training/evaluation also require explicit admission.
- Select free hosting/database tiers explicitly and verify limits before deployment. No purchases, paid upgrades or new hardware without approval.

Review all public recordings/screenshots for secrets and private data. If photos are added later, remove metadata and separately inspect visual identifiers: stripping metadata does not anonymize an image.

## Training and evaluation

Train a fresh OneLap LoRA adapter only after base Qwen works through the complete loop, data is reviewed and a training/evaluation budget is separately approved. The resumed API workflow now passes, but quality and field usefulness remain unproven. Targets: respect time/activity restrictions; use supplied observations without inventing surroundings; avoid recent repetitions; adapt to feedback; express uncertainty; produce concise structured missions/reflections.

Initial target: approximately 80-100 reviewed synthetic training examples, about 20 development cases and 30 held-out cases. Split scenario families before generating variants. Label provenance/review status and never present synthetic examples as actual outings. Do not use held-out cases to iterate prompts or training.

Establish a base-Qwen baseline, then compare with the tuned model under identical application checks, memory inputs, decoding and scoring. Record model identity, checkpoint, dataset hashes, parameters, failures and run conditions. Do not automatically promote a trained adapter.

Report constraint compliance, unsupported claims, repetition, grounded/adaptive usefulness, structured-output validity, latency and estimated token costs separately, with denominators and limitations. Use deterministic checks where possible and a documented human rubric for semantic judgments. Exact wording agreement is not mission quality; avoid a vague overall accuracy figure.

Tinker category eligibility requires an actual improvement over a baseline, not training completion alone. If tuning does not improve evaluated results, report that honestly and retain the better validated model. Training must not prevent submission.

Outdoor evidence: two short outings, preparation time, phone interactions, mission suitability, and whether the reflection matched the actual observation. Record failures and changes. This is a small personal test, not proof of broad behaviour change. Never invent field results or feedback.

## Functional increments

1. **Base-model mission generation:** structured schema, real Tinker adapter, validation, limits and failure tests. First hosted request waits for data/spending approval.
2. **Phone mission experience:** mobile UI, honest loading/errors, saved mission and offline access; verify on an actual phone.
3. **Persistent outing memory:** protected Atlas journal/feedback, reliable offline synchronization and deletion.
4. **Adaptive follow-ups:** implemented and pushed in `c356fe7`. The initial live fictional-data request was rejected for focus drift. A separately approved `follow-up-v2` retest during increment 9 accepted all four source selections, using one captured mission and a fresh isolated Atlas note with verified deletion. Semantic quality, live browser/phone and field verification remain pending. The service retrieves only selected notes and handles schema/policy constraints and exact repeats.
5. **Protected deployment package:** pushed as `b7d2dee`: build the frontend/API together, keep private API routes behind a required server token, configure hosted-data/model gates off, disable auto-deploys and document free-tier persistence limits. Actual Render deployment/browser connectivity remains pending.
6. **Integration verification:** a preflight/live smoke command checks fictional missions, isolated Atlas write/read/idempotency, follow-up generation, deletion and replay rejection; it reports timings, provenance, cleanup, bounded synthetic replies and existing spend reservations. Validated resumption avoids unnecessary mission requests. Four approved samples are used. One initial mission and a resumed revised follow-up passed; this verifies the checked API workflow, not a fresh two-generation/browser/phone or semantic-quality result. Further live testing needs new approval; the ledger must not be reset.
7. **Private diagnostic tracing (optional):** pushed as `c6db1c6`, with root/child spans for retrieval, inference, validation and persistence. Real SDK envelopes pass an allowlist/privacy test using a non-network collector. Export requires two separate gates and a private DSN; both gates stay off. Actual Sentry ingestion/dashboard evidence remains unverified.
8. **Training/evaluation tooling:** offline preparation/replay and matched-comparison guards are pushed as `953a4bf`. The 18 family-separated seed inputs remain assistant-authored and unreviewed; they are not training targets or a sufficient benchmark. Human review/expansion, genuine baseline captures, an approved LoRA pilot and actual comparison remain pending. API integration now passes, but training still needs data review and a separate budget. See docs/evaluation.md.
9. **Captured-mission handoff:** pushed as `0047c60`: preview/review/save a bounded JSON entirely on-device, retain unverified imported provenance offline, preserve current mission on failure, and keep existing notes. Includes one unmodified, cross-checked live synthetic capture and an unfilled phone/outdoor/demo checklist. No new API route or automatic sample/upload.
10. **No-spend field-test kit / submission evidence:** approved and pushed as `07f19e2`: isolated static preview/guide/download with no API proxy, USB-only Android setup instructions, reproducible labelled desktop capture-playback recording, request/hash manifest and DEV draft. The service worker leaves handoff/download routes uncached and reachable after app caching. At this boundary, 24 server tests, 158 frontend tests, 363 backend tests, five existing production browser checks and the recorded walkthrough pass. The locally generated 42-second video remains ignored and needs full user review before publication. Physical-phone/installation and actual outdoor results are pending for the user's planned outing tomorrow. README/post/video publication must describe actual results and category use, not simulated outings.
11. **Fresh production-browser integration harness:** implemented locally: default read-only preflight, no-env/no-spend fixture mode and separately consent-gated live mode. A disposable browser tests real UI/API over protected loopback HTTP, using a fresh test owner and one exact fictional note. It verifies offline saves/reloads, explicit sync/readback, reviewed follow-up/acceptance, deletion and next-mission offline reload. Cleanup tracks attempted writes before storage and checks deletion/replay even after browser failure. Request allowlists, two-generation ceiling and credential-free children preserve scope. The real Windows MIME bug discovered by this test is fixed in the production static-file handler. The fixture run passes; no new hosted request is authorized or made. See docs/browser-smoke.md and docs/increment-11.md. Fresh commit/push approval is required.

One functionality per commit. Adapt increment size as necessary. Every commit and every push requires explicit user approval. Before requesting approval, summarize changes and verification. No automatic commits, pushes, PRs, account creation or public posting. No coauthor/editor attribution in commit messages. GuardMate must remain untouched.

## Schedule and submission

Targets: complete core loop by October 8; freeze features October 9; outdoor tests, demo and draft October 10; October 11 remains a buffer. These are targets, not guarantees.

Published challenge close: October 11, 2026 at 11:59 PM PDT, equivalent to October 12 at 12:29 PM IST. Rechecked on the [official challenge page](https://dev.to/challenges/hacktoberfest-week1-2026-10-05) on October 10; recheck before publication and keep the earlier internal target. Required DEV tags: `devchallenge`, `hf26challenge`.

Target categories: Tinker, MongoDB Atlas, Render and Sentry, only where implemented and demonstrated. Multiple eligible categories do not mean multiple wins. The writing and genuine screen-light outdoor experience remain central. Start and complete the new repository within the challenge window; note post-deadline commits as required by the rules.

## Deferred

Gemma/local photo understanding, ElevenLabs narration, voice recording, GPS/routes/maps, social features, streaks, vector search, multiple orchestrators, hardware integrations and extra hosting providers. Revisit only after the core loop and field evidence are complete.

## Resume checklist

- Increment 1 now contains the Python backend scaffold, typed mission generation, Tinker SDK adapter, application checks, bearer-token access, payload/rate limits and persistent estimated-spend reservations. Its own virtual environment and offline tests are set up. See README.md for commands and current limitations.
- Verification: 200 offline tests, Ruff lint/format and dependency checks passed. Real loopback HTTP health/setup behaviour was smoke-tested with hosted requests disabled; the temporary server was stopped. Full details: docs/increment-1.md.
- Increment 2 adds a component-based React phone interface, private connection controls, explicit hosted-selection consent, honest loading/errors, IndexedDB mission saving, minimal pocket view and production service-worker app caching. Saved missions appear before the preparation form. Tokens remain memory-only; private API responses are never precached.
- Increment 2 verification: 71 frontend tests, 3 production-browser checks (offline reload using a labelled fixture, responsive sizes, disabled-provider gate), type checking/build/formatting and the existing 200 backend tests passed. The actual disabled API/proxy setup error was checked in the browser. Physical-phone testing/install prompts remain pending. Details: docs/increment-2.md.
- Increment 3 adds offline observation/feedback capture, IndexedDB v2 migration, a durable owner-bound outbox, explicit sync consent, Atlas storage/pagination and content-free deletion tombstones that block replay. At the user's request, local setup no longer needs a manual owner ID or access token: a stable personal journal ID is automatic, and no-token requests are loopback-only with host/origin/proxy checks. Optional configured bearer protection remains for future non-local use. This is not multi-user login. A separately authorized authenticated Atlas ping passed, with no journal data uploaded. Setup instructions: docs/atlas-setup.md; implementation details: docs/increment-3.md.
- Increment 3 verification: 253 offline backend tests, 121 frontend tests and 4 production-browser checks passed, including offline note reload, lost-response retry without duplication and confirmed deletion. Type/build/format/lint/dependency checks pass. Database tests use offline doubles, not Atlas. No outdoor results are claimed.
- Increment 4 adds a server-checked selection of one completed Atlas note and up to two optional context notes, an explicit review/consent UI, owner-scoped re-read from Atlas, a separately gated Qwen/Tinker request, and a review-before-saving response. `ONELAP_REFLECTION_SHARING_APPROVED` defaults off. Only selected outcome/feedback/observation/mission fields enter the model prompt. Offline verification passed: 261 backend tests, 123 frontend tests, Ruff, Prettier, TypeScript, production build and four Edge browser checks. No live Atlas or inference call was made. Commit `c356fe7` was pushed to `main`.
- Increment 5 adds a one-container frontend/API deployment package. The Render Blueprint uses the free plan, `autoDeployTrigger: off`, a manually entered server-only access token, and disabled Tinker/Atlas/reflection gates. Since free Render storage is ephemeral and cannot preserve the file-based spend ledger, hosted model use must remain off in this template. No Render service has been created, and public browser connectivity is unverified. Offline verification: 264 backend tests, 123 frontend tests, Ruff, Prettier, TypeScript and production build pass. Docker image build was not possible because no local daemon is available; Render CLI is not installed. See `docs/increment-5.md` for limitations. Commit `b7d2dee` was pushed to `main` on October 10.
- Increment 6 adds the repeatable smoke command, bounded synthetic response capture, validated report resumption and isolated fictional-data workflow. 282 backend tests, 126 frontend tests and four fixture-based Edge browser checks pass, with Ruff, Prettier, TypeScript and production build checks. AI dependencies are installed, both credentials are present, and `pip check` passes. Saved model/Atlas gates remain off; only approved subprocesses enabled them. Three actual samples used an estimated $0.002278 reservation under the $0.05 test cap. One mission was accepted; live Atlas storage/idempotency/readback/owner/deletion/replay checks passed and test content was removed. The live follow-up changed focus and was rejected. The new prompt has only local regression coverage, not a successful live check. See `docs/increment-6.md` and `docs/live-smoke-2026-10-10.md`.
- Increment 6 was committed and pushed as `05ec0a8` on October 10 with the user's approval.
- Increment 7 adds metadata-only diagnostic tracing, SDK output-token counting, private configuration and disabled Render defaults. 308 backend tests (including 26 real-SDK, non-network tracing tests), 126 frontend tests, Ruff, Prettier, TypeScript, production build and dependency checks passed. SDK spans/envelopes were checked locally; no Sentry upload or extra model/database request was made. See `docs/increment-7.md` and `docs/tracing-setup.md`. It was committed and pushed as `c6db1c6` on October 10 with the user's approval.
- Increment 8 implements an offline evaluation kit: schema/family validation, exact app-prompt manifests, replay via shared application checks, human rubric and hash-bound reviews, complete-case accounting and matched comparison with fixture/review/identity/decoding/runtime guards. The 18 seed cases are unreviewed and synthetic, six per split, without gold targets. At this increment's boundary, 363 backend tests, Ruff, CLI validate/prepare and dependency checks passed; frontend was unchanged. No hosted requests or ledger changes occurred during increment 8. See `docs/increment-8.md` and `docs/evaluation.md`. It was committed and pushed as `953a4bf` with the user's approval on October 10.
- Increment 9 adds local mission-file handoff with explicit review, bounded schema/duplicate/keyword checks, persistent imported labels, safe replacement and old-save compatibility. At its boundary, 155 frontend tests, five production Edge checks, TypeScript/build/Prettier, 363 backend tests and Ruff/dependency checks passed. The new browser test is entirely offline with zero private API calls; no physical-phone result is claimed. A public example matches the actual captured response, with known semantic defects preserved. See `docs/increment-9.md`, `examples/README.md` and `docs/field-test.md`. It was committed and pushed as `0047c60` on October 10 with approval.
- The separately approved fourth sample used only one `follow-up-v2` request and reused the previous mission. Real Atlas upload/idempotency/readback/owner/deletion/replay and follow-up acceptance passed. Its test observation was removed and saved gates stayed off. The preserved ledger is four samples/$0.003103 estimated, not actual billing. The additional request is used; no more calls are authorized. Formal human review and field usefulness remain pending.
- Increment 10 adds the no-spend phone/demo kit and DEV draft. The static preview has no backend/proxy and accepts only explicit public files; the USB procedure changes no hardware settings by itself. A 42-second, phone-width desktop video verifies captured-file download/import, pocket mode, browser-offline mission reload and fictional skipped-note persistence with zero private API attempts/errors. Its checkpoint screenshots were visually inspected; full video review/upload approval remains with the user. Video/manifests/dependency binaries are ignored in `.data`; no shared/personal journal is read. The guide/download remain reachable after service-worker control and uncached. Verification at its boundary: 24 Node server tests, 158 frontend tests, 363 backend tests, five existing Edge checks, TypeScript/build/Prettier, Ruff/dependency checks. See `docs/increment-10.md`, `docs/phone-setup.md`, `docs/demo.md` and `docs/submission-draft.md`. It was approved and pushed as `07f19e2` on October 10.
- Increment 11 adds the real packaged-server browser harness, isolated fixture/live modes and deterministic public MIME types. Its local Edge fixture loop passes all seven stages with zero blocked requests/page errors and verified cleanup; it is not a live-provider result. Verification: 386 backend tests, 158 frontend tests, 24 static-handoff tests, nine request-boundary tests, TypeScript/build/Prettier and Ruff/dependency checks. Local reports/screenshots remain ignored. Saved gates and the real four-request ledger are unchanged. This increment is uncommitted; fresh commit/push and live-data/spending approvals are separate.
- No hosted evaluation, training, live Sentry export, public deployment or outdoor test has been performed. Latest pushed baseline: `07f19e2`. Future commits/pushes still require new approval.
- Approved repository: https://github.com/DivyanshSaharan/OneLap.git. Keep the project and Git history separate from GuardMate.
- Read this plan and any new AGENTS.md instructions before continuing.
- Next steps: request fresh approval before committing/pushing increment 11, and separately approve up to two additional synthetic Tinker samples plus the isolated Atlas entry before a fresh live browser loop. Use docs/browser-smoke.md; keep the existing cumulative $0.05 estimated cap, preserve the four used reservations, enable only temporary child-shell gates, and never auto-retry an invalid reply. The user plans a phone check/outing tomorrow; follow `docs/phone-setup.md` and fill genuine evidence in `docs/field-test.md`, without claiming results early or forcing an unsuitable evening capture into a different outing. A new personalized mission/reflection still needs separate data/spending approval. Review the full local video, choose/approve publication and add its real public URL to the README/DEV draft; nothing is posted automatically. Before training, review/expand/freeze seed data and agree a separate training/evaluation budget. Do not use held-out replies for prompt/target iteration. Any new hosted test, personal-note sharing, Sentry upload/project setup or Render creation requires separate authorization. Use the existing ledger and preserve ignored reports; never reset counters for more allowance.
- User time/token budget is limited. Keep updates concise and stop at approval boundaries.

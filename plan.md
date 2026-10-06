# OneLap: implementation and handoff plan

Recorded: October 6, 2026. Status: increments 1 and 2 implemented; desktop-browser offline reload verified, physical phone and live inference pending.

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
| Hosting | Render frontend and lightweight API |
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

Scope every read/write to the authenticated owner. Use stable IDs and idempotent synchronization to prevent duplicates. Pending observations must survive reloads, show sync status and not silently overwrite newer data. Completion is user-reported; opening a mission is not completion.

## Privacy, security and cost boundaries

- No precise-location field or GPS permission.
- Journal text/preferences are stored in Atlas; relevant observations/history go to Tinker. Disclose both clearly.
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

Train a fresh OneLap LoRA adapter only after base Qwen works through the complete loop. Targets: respect time/activity restrictions; use supplied observations without inventing surroundings; avoid recent repetitions; adapt to feedback; express uncertainty; produce concise structured missions/reflections.

Initial target: approximately 80-100 reviewed synthetic training examples, about 20 development cases and 30 held-out cases. Split scenario families before generating variants. Label provenance/review status and never present synthetic examples as actual outings. Do not use held-out cases to iterate prompts or training.

Establish a base-Qwen baseline, then compare with the tuned model under identical application checks, memory inputs, decoding and scoring. Record model identity, checkpoint, dataset hashes, parameters, failures and run conditions. Do not automatically promote a trained adapter.

Report constraint compliance, unsupported claims, repetition, grounded/adaptive usefulness, structured-output validity, latency and estimated token costs separately, with denominators and limitations. Use deterministic checks where possible and a documented human rubric for semantic judgments. Exact wording agreement is not mission quality; avoid a vague overall accuracy figure.

Tinker category eligibility requires an actual improvement over a baseline, not training completion alone. If tuning does not improve evaluated results, report that honestly and retain the better validated model. Training must not prevent submission.

Outdoor evidence: two short outings, preparation time, phone interactions, mission suitability, and whether the reflection matched the actual observation. Record failures and changes. This is a small personal test, not proof of broad behaviour change. Never invent field results or feedback.

## Functional increments

1. **Base-model mission generation:** structured schema, real Tinker adapter, validation, limits and failure tests. First hosted request waits for data/spending approval.
2. **Phone mission experience:** mobile UI, honest loading/errors, saved mission and offline access; verify on an actual phone.
3. **Persistent outing memory:** protected Atlas journal/feedback, reliable offline synchronization and deletion.
4. **Adaptive follow-ups:** history retrieval, grounded reflection and a non-repetitive next mission; handle unsuitable tasks.
5. **Protected deployment:** Render configuration, server-side secrets, access/data isolation and actual browser connectivity.
6. **Private diagnostic tracing:** Sentry spans for retrieval, inference, validation and persistence; verify no private-content exports.
7. **Training/evaluation tooling:** reviewed splits, baseline, budgeted LoRA pilot, matched comparison and promotion decision.
8. **Submission evidence:** outdoor tests, reviewed demo, README and DEV post with limitations and actual category usage.

One functionality per commit. Adapt increment size as necessary. Every commit and every push requires explicit user approval. Before requesting approval, summarize changes and verification. No automatic commits, pushes, PRs, account creation or public posting. No coauthor/editor attribution in commit messages. GuardMate must remain untouched.

## Schedule and submission

Targets: complete core loop by October 8; freeze features October 9; outdoor tests, demo and draft October 10; October 11 remains a buffer. These are targets, not guarantees.

Published challenge close: October 11, 2026 at 11:59 PM PDT, equivalent to October 12 at 12:29 PM IST. Reverify official rules before publication; keep the earlier internal target. Required DEV tags: `devchallenge`, `hf26challenge`.

Target categories: Tinker, MongoDB Atlas, Render and Sentry, only where implemented and demonstrated. Multiple eligible categories do not mean multiple wins. The writing and genuine screen-light outdoor experience remain central. Start and complete the new repository within the challenge window; note post-deadline commits as required by the rules.

## Deferred

Gemma/local photo understanding, ElevenLabs narration, voice recording, GPS/routes/maps, social features, streaks, vector search, multiple orchestrators, hardware integrations and extra hosting providers. Revisit only after the core loop and field evidence are complete.

## Resume checklist

- Increment 1 now contains the Python backend scaffold, typed mission generation, Tinker SDK adapter, application checks, bearer-token access, payload/rate limits and persistent estimated-spend reservations. Its own virtual environment and offline tests are set up. See README.md for commands and current limitations.
- Verification: 200 offline tests, Ruff lint/format and dependency checks passed. Real loopback HTTP health/setup behaviour was smoke-tested with hosted requests disabled; the temporary server was stopped. Full details: docs/increment-1.md.
- Increment 2 adds a component-based React phone interface, private connection controls, explicit hosted-selection consent, honest loading/errors, IndexedDB mission saving, minimal pocket view and production service-worker app caching. Saved missions appear before the preparation form. Tokens remain memory-only; private API responses are never precached.
- Increment 2 verification: 71 frontend tests, 3 production-browser checks (offline reload using a labelled fixture, responsive sizes, disabled-provider gate), type checking/build/formatting and the existing 200 backend tests passed. The actual disabled API/proxy setup error was checked in the browser. Physical-phone testing/install prompts remain pending. Details: docs/increment-2.md.
- No Atlas journal, training, deployment or Sentry export is implemented yet. No paid model requests have been performed. Increment 1 is committed and pushed as `171543d`; the user approved increment 2's commit and push on October 6. Consult Git history for its publication state.
- Approved repository: https://github.com/DivyanshSaharan/OneLap.git. Keep the project and Git history separate from GuardMate.
- Read this plan and any new AGENTS.md instructions before continuing.
- Next implementation increment after commit approval: protected outing journal/feedback, local observation outbox and idempotent Atlas synchronization. Atlas provisioning/credentials and the journal data boundary require the owner's participation; do not create accounts or transmit journals without authorization. Physical-phone testing remains an open verification item for increment 2.
- Obtain the hosted-data/spending decision and configure OneLap credentials privately before live requests.
- User time/token budget is limited. Keep updates concise and stop at approval boundaries.

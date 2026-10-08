# Increment 4: selected-history reflection and follow-up

Status: implemented and verified offline. No live Atlas operation or Tinker request has been run for this increment.

## User flow

1. The user explicitly checks follow-up availability. The status endpoint checks configuration and budget state only; it does not query Atlas or initialize the Tinker sampling client.
2. The user chooses one completed observation and may select up to two earlier completed observations already loaded from Atlas.
3. The UI displays the full observation text, outcome, feedback and mission summary for every selected record. The recording timestamp is shown for reference but is not included in the Qwen prompt. Journal IDs are sent to the API for retrieval, but are not included in the prompt.
4. A separate checkbox approves this one request. The browser sends the selected IDs only. The server verifies the configured journal owner, reloads the exact non-deleted records from Atlas and checks all selected records are completed outings with observations; optional context must predate the primary note.
5. One Qwen/Qwen3.5-4B sample is requested through Tinker. The prompt treats notes as untrusted data, requires a short reflection and mission schema, and preserves the source mission's duration, setting, conditions and focus. Application validation and an exact-repeat guard run before returning the result.
6. The UI labels the output as model-generated, shows the source count and lets the user accept or discard the suggestion. Accept saves the mission locally first; it does not upload a new journal entry. A storage failure leaves the current mission in place.

## Data and cost gates

Follow-up requires all existing provider, hosted-request, data-sharing, budget/request-count and Atlas gates, plus `ONELAP_REFLECTION_SHARING_APPROVED=true`. The new setting is false by default in `.env.example`. No live call has been made and the local server settings have not been changed.

After approval, selected outcome, feedback, observation text and mission summary are sent to hosted Qwen through Tinker. They may contain sensitive information; review before approval and do not include precise locations or private details in journal notes. Check current Tinker retention and terms before enabling. Each sample consumes the existing estimated-spend reservation. It is an estimate, not a provider billing guarantee. There is no automatic retry.

The checkbox is a UI-level per-request disclosure, not a stored consent receipt or a cryptographic authorization. The server-side setting is a global gate. Keep the API private and loopback-only for personal use; do not expose a paid-inference endpoint publicly.

## Limits

- Model output and source IDs are returned to the UI; the source IDs are not yet persisted alongside the accepted mission as durable provenance.
- The checks validate shape, allowed settings and application restrictions; they do not prove that a reflection is factually grounded or that a mission is safe or suitable.
- This is one shared personal journal, not multi-user authentication. Device notes are not encrypted. Atlas or model-provider backups/retention may outlive local deletion.
- A successful status check does not prove Atlas availability or validate selected records. These are checked only when the user submits the request.
- Physical-phone behavior, live Atlas read/write/delete, model quality, training comparison and field results remain unverified.

## Files

- Backend: a distinct reflection-sharing gate, owner-scoped selection of Atlas records, bounded follow-up prompt/output validation, Qwen/Tinker sampling and a separate follow-up API.
- Frontend: explicit readiness check, selected-note and context review, per-request consent, generated-result review, accept/discard controls and local mission save.
- Documentation: README and plan describe the new data boundary and current verification limits.

## Verification

Verification passed: 261 backend tests, 123 frontend tests, Ruff check/format, Prettier, TypeScript, production build and all four existing Playwright checks using installed Edge. Follow-up-specific tests cover prompt data boundaries, selected-record ownership/order, server gate behavior, constraints, exact repetition, context chronology, and UI selection/consent. Browser checks use fictional fixtures; none call Atlas or Qwen. Live Atlas operations and model quality remain unverified. Commit and push status is recorded in Git history.

# Increment 7: private diagnostic tracing

Implemented locally; not committed or pushed yet. Increment 6 was pushed as `05ec0a8`. This increment makes workflow timings and validation failures inspectable without exporting personal observations or model text.

## Instrumentation

Mission and follow-up API calls get a manually created `gen_ai.invoke_agent` root. Child spans cover runtime/tokenizer setup, encoding, estimated-spend admission, one `gen_ai.chat` sample, parsing and validation. Follow-ups include a `gen_ai.execute_tool` span for selected Atlas retrieval. Journal upload, loading and deletion have separate roots with database-operation spans. Health, configuration status, authentication rejection and requests rejected before route execution are not traced.

This instruments OneLap's structured workflow; it does not add autonomous behavior or change model responses. Existing restrictions, consent gates, request limits, reservations and no-retry behavior are unchanged.

## Metadata boundary

Only fixed operation/model/provider/prompt-version labels, known public failure codes, timestamps, anonymous SDK-generated trace/span IDs, bounded token counts and the number of selected records are retained. Output usage is included only when returned token IDs were actually counted; missing usage is omitted. `onelap.estimated_reserved_usd` appears only after a successful reservation and is not a measured cost or a `gen_ai.cost.*` attribute.

No mission/reflection/observation text, outcome/feedback, chosen setting/focus, journal/mission IDs, URLs, queries/URIs, headers, credentials, user identifiers, variables, stack traces, exception messages, breadcrumbs, logs, profiles, session reports or device/host context are retained in the transaction payload. The destination still observes the network connection's source IP; removing payload fields does not make an upload anonymous.

`ONELAP_TRACING_ENABLED` and `ONELAP_TRACE_SHARING_APPROVED` default to `false`. A DSN alone does nothing. Disabled tracing imports no SDK and creates no client. Enabling it does not enable Tinker, reflection sharing or Atlas.

The pinned `sentry-sdk==2.71.0` client uses operation-local scopes, not global initialization. Automatic integrations and ancillary reporting channels are disabled. The final `before_send_transaction` hook rebuilds the payload from strict field/value allowlists, stripping inherited scope data and unknown fields/spans. Both `trace_lifecycle="static"` and `stream_gen_ai_spans=False` are explicit so AI spans pass through that filter instead of leaving separately. Official references: [manual instrumentation](https://docs.sentry.io/platforms/python/agent-tracing/manual-instrumentation/), [filtering](https://docs.sentry.io/platforms/python/configuration/filtering/), and [configuration](https://docs.sentry.io/platforms/python/configuration/options/).

Tracing is best-effort: an operation-time instrumentation/export failure does not change application results or cause another sample. Explicitly enabling tracing without its dependency fails startup with a safe setup message. Shutdown flush is bounded to two seconds; this is not a durable audit log.

## Verification and limitations

308 offline backend tests pass, including 26 tracing tests. They use the actual SDK with an in-memory transport and explicitly forbid HTTP transport construction. Tests inspect serialized envelopes, not just a mocked sanitizer. Coverage includes both gates, DSN errors, inherited private scope, unexpected fields, measured/missing usage, provider failure reservations, the observed focus-drift rejection, journal operations, thread-local parentage, instrumentation/export failures and untraced health/status/authentication requests. The SDK adapter contract also verifies returned-token counting.

126 frontend tests, TypeScript, production build, Prettier, Ruff lint/format and `pip check` pass. The frontend is unchanged. Four fixture-based Edge checks passed in increment 6, not as a new live telemetry or phone test. No Docker image was built; no local daemon is available.

Saved tracing gates are off and no DSN is configured. No Sentry project has been created, no envelope has been uploaded, and no additional Tinker/Atlas request was made for this increment. A received dashboard trace/screenshot remains pending, so partner-category evidence is not complete. See [tracing-setup.md](tracing-setup.md) for the separate upload-approval boundary.

# Optional Sentry setup

Tracing is not required to use OneLap. The implementation is tested with the real SDK and an in-memory collector; Sentry ingestion/dashboard behavior has not been verified.

## Keep export off during setup

These settings in the ignored `.env` have the same defaults if absent:

```dotenv
ONELAP_TRACING_ENABLED=false
ONELAP_TRACE_SHARING_APPROVED=false
ONELAP_SENTRY_DSN=
```

Keep the DSN out of chat, source code, frontend variables and recordings. Only a project ingestion DSN is used, never a Sentry account API token. This prototype accepts HTTPS DSNs on `*.sentry.io`, not self-hosted endpoints.

Development requirements include the SDK for privacy tests. An existing backend environment can install it separately:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-tracing.txt
```

Docker also installs it, but Render's template leaves both gates off and contains no DSN. Package installation does not authorize telemetry uploads.

## Before a live upload

1. Choose a Sentry Python project that you control; review its quotas and retention. No account/project creation, purchase or upload has been performed here.
2. Store the project's DSN privately, keeping both gates off.
3. Review [the metadata boundary](increment-7.md): timestamps, anonymous trace IDs, fixed labels, usage counts, selected-record count, reservation estimates and known failures can leave the laptop. Journal/model text cannot.
4. Agree a fictional test and its scope before setting both gates to `true` for that run. Restart the API after configuration changes. Leave Tinker/Atlas gates unchanged without their separate data/spend approval.
5. Inspect the received transaction and every child span before taking a reviewed screenshot. Check that prompts, headers, URLs, user/host context and observations are absent.
6. Restore both gates to `false` and restart afterward. Existing remote events remain subject to Sentry's retention/deletion behavior.

The standalone smoke runner injects local app settings and leaves tracing disabled, even if `.env` contains tracing settings. Test telemetry deliberately through a tracing-enabled API instance; a smoke report does not prove Sentry ingestion.

## Reading traces

The `mission` and `followup` pipelines have separate root metadata. Retrieval precedes sampling, and validation follows it. This distinguishes database delay, cold setup, inference and rejected output. `mission_constraint_mismatch` differs from provider failure, even though neither produces an accepted mission.

Input counts come from the tokenizer. Output counts are returned token IDs when available, not character estimates. `onelap.estimated_reserved_usd` is local admission, not billing. Any costs Sentry derives from model/usage attributes are estimates, not invoices or remaining promotional credit.

There is no frontend replay/tracing, conversation/user ID or automatic exception reporting. New metrics require tested allowlist changes. Events may be lost after crashes or transport failures; tracing does not replace the spending ledger.

References: [Sentry Agent Tracing](https://docs.sentry.io/platforms/python/agent-tracing/), [manual spans](https://docs.sentry.io/platforms/python/agent-tracing/manual-instrumentation/), [filtering hooks](https://docs.sentry.io/platforms/python/configuration/filtering/).

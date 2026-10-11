# Next deployment boundary

The authorized non-auth preparation is complete: durable Atlas spending reservations, device/journal-scoped storage, a frozen synthetic corpus, matched baseline/adapter captures, one capped LoRA pilot, verified checkpoint selection and simplified production controls. These are committed separately. The app remains base-model/default-off; no deployment service or authenticated account system was created.

## What still needs the owner

1. **Google authentication and per-user cloud authorization**, explicitly excluded from this run. Supply OAuth client configuration privately after that feature is approved. A UUID device slot or shared server token is not a login; all current authorized clients use the same personal cloud identity.
2. **Actual Render deployment approval/configuration.** Reuse the Docker/Blueprint package, supply server-side secrets only, keep automatic deploys off and review the HTTPS origin/OAuth redirect settings. Do not publish paid access until authentication/owner isolation passes.
3. **Durable budget import/activation.** Read the current file ledger again, explicitly import both counters into the stable production Atlas scope, and approve its separate metadata gate and cumulative model limits. The live probe did not migrate it. Never reset old counters to regain allowance.
4. **Container build and HTTPS smoke.** Docker's Linux engine is currently unavailable. The packaged server/browser works locally, but a Docker build and real Render health/static/API test remain unverified. No account or service was created to work around that boundary.
5. **Human review and field/demo evidence.** The measured gain is application acceptance on synthetic variants, not enjoyable/grounded outings. Review model replies, do the physical-phone/offline/outdoor check, review/upload the demo and supply its real public link before publishing the DEV draft.

No additional paid sample or second training candidate is authorized simply because the pilot left headroom. The seven-day sampler TTL may expire before later testing; do not silently retrain or change the model. Raw reports, receipt, sampler path, API keys and journals remain ignored. The user reported $0.23 combined account usage before this run; obtain a new provider billing snapshot to learn actual remaining credit.

## Resume checks

Read the current top of `plan.md`, inspect Git status/history, confirm `.env` gates without printing credentials, and preserve both `.data/inference-budget.json` and `.data/experiments/experiment-budget.sqlite3`. Standard tests are offline and do not create a hosted client. Do not modify prompts/validators and reinterpret the frozen pilot as if it used those later changes; any future benchmark needs a distinct documented method and new allowance.

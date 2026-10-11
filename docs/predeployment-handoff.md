# Deployment activation handoff

The owner subsequently approved explicit Atlas journal sync. The two Render
journal gates are saved and read back; uploads still require the user's per-sync
selection. A fresh signed-in browser can open the cloud journal without creating
a mission. Reflection sharing and tracing remain off, and no new model request or
personal-note upload is implied by this configuration change. See [Atlas sync](atlas-sync.md).

Authentication/per-user journals are pushed in `e9679a8`; the owner reports local login/logout works. Header sign-in, user-facing copy cleanup and importer removal are pushed in `8c12caf`. The Docker image builds and its network-disabled smoke checks, real receipt loading and group-1000 secret-file permission controls pass. The existing Render service at [onelap-4s17.onrender.com](https://onelap-4s17.onrender.com) returned health HTTP 200 on release `7cad60b`. Health does not prove signed-in generation, model availability or outdoor usefulness.

On October 11, the owner approved mission-only activation and the necessary Render settings under the existing cumulative **$0.05 / 20-request** limits. The production Atlas counter was initialized in `onelap.inference_spending`, scope `onelap:inference:v1`, with **$0.004665 / six requests**; reopen readback matches and the source ledgers are unchanged. This leaves at most 14 admissions within the estimated remaining $0.045335, not a fresh allowance. No model request was made. The exact Render overrides are saved and read back; a production-Atlas status preflight reports the trained adapter enabled without constructing a Tinker client. Paid remote sampling remains unverified. Journal upload, Atlas-note sharing, reflection sharing and tracing stay off.

## What still needs the owner

1. **Review and user-driven Google login verification.** OAuth credentials are in the ignored `.env`; implementation uses Google popup sign-in, verified ID tokens and revocable Atlas sessions. Check login/reload/logout and a second account without submitting a mission or syncing notes. Existing personal history is not migrated. See docs/authentication.md.
2. **Verify the approved Render release.** The hosted-request, generic-data and budget gates retain the exact import values; explicit journal sync is separately approved. Release checks must verify the deployed commit and readiness without sampling. Preserve the verified uploaded LF receipt hash and every unrelated secret. Reflection and trace sharing stay off. The checked-in Blueprint retains safe disabled defaults for a new service.
3. **Preserve the durable budget.** Production initialization is complete, not pending. Keep the same Atlas database, collection, scope and immutable import across deployments. Do not resume independent local file-ledger spending or reset either counter to regain allowance. See docs/budget.md.
4. **Complete Render HTTPS readiness checks.** Check assets and anonymous protected-route rejection without sampling, then have the owner verify real Google login/reload/logout and the signed-in model status. A status check does not contact Tinker; remote adapter availability and generation remain unverified until a separately approved/user-driven request. See docs/docker-deployment.md.
5. **Human review and field/demo evidence.** The measured gain is application acceptance on synthetic variants, not enjoyable/grounded outings. Review model replies, do the physical-phone/offline/outdoor check, review/upload the demo and supply its real public link before publishing the DEV draft.

No automated paid sample or second training candidate is authorized simply because activation is approved or the pilot left headroom. The seven-day sampler TTL may expire before later testing; do not silently retrain or change the model. Raw reports, receipt, sampler path, API keys and journals remain ignored. The user reported $0.23 combined account usage before this run; obtain a new provider billing snapshot to learn actual remaining credit.

## Resume checks

Read the current top of `plan.md`, inspect Git status/history, confirm `.env` gates without printing credentials, and preserve both `.data/inference-budget.json` and `.data/experiments/experiment-budget.sqlite3`. Standard tests are offline and do not create a hosted client. Do not modify prompts/validators and reinterpret the frozen pilot as if it used those later changes; any future benchmark needs a distinct documented method and new allowance.

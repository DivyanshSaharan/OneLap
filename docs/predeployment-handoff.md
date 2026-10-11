# Next deployment boundary

Authentication/per-user journals are pushed in `e9679a8`; the owner reports local login/logout works. Header sign-in, user-facing copy cleanup and importer removal are pushed in `8c12caf`. Docker/Compose preparation is now implemented locally: the Linux image builds, its network-disabled smoke checks and real receipt loading pass. The owner approved pushing Docker preparation and selecting the trained adapter in separate commits. Spending/sharing gates remain off; no deployment service was created.

## What still needs the owner

1. **Review and user-driven Google login verification.** OAuth credentials are in the ignored `.env`; implementation uses Google popup sign-in, verified ID tokens and revocable Atlas sessions. Check login/reload/logout and a second account with sharing/model gates off. Existing personal history is not migrated. See docs/authentication.md.
2. **Actual Render deployment approval/configuration.** Reuse the Docker/Blueprint package, supply server-side secrets only, keep automatic deploys off and review the HTTPS origin/OAuth redirect settings. Do not publish paid access until authentication/owner isolation passes.
3. **Durable budget import/activation.** Read the current file ledger again, explicitly import both counters into the stable production Atlas scope, and approve its separate metadata gate and cumulative model limits. The live probe did not migrate it. Never reset old counters to regain allowance.
4. **Render HTTPS smoke.** The Docker Linux engine is running and the local image build, health/static/auth smoke, non-root receipt loading and dependency checks pass. Real Render health/assets/authentication and secret-file permission checks remain unverified. See docs/docker-deployment.md; no account or service was created.
5. **Human review and field/demo evidence.** The measured gain is application acceptance on synthetic variants, not enjoyable/grounded outings. Review model replies, do the physical-phone/offline/outdoor check, review/upload the demo and supply its real public link before publishing the DEV draft.

No additional paid sample or second training candidate is authorized simply because the pilot left headroom. The seven-day sampler TTL may expire before later testing; do not silently retrain or change the model. Raw reports, receipt, sampler path, API keys and journals remain ignored. The user reported $0.23 combined account usage before this run; obtain a new provider billing snapshot to learn actual remaining credit.

## Resume checks

Read the current top of `plan.md`, inspect Git status/history, confirm `.env` gates without printing credentials, and preserve both `.data/inference-budget.json` and `.data/experiments/experiment-budget.sqlite3`. Standard tests are offline and do not create a hosted client. Do not modify prompts/validators and reinterpret the frozen pilot as if it used those later changes; any future benchmark needs a distinct documented method and new allowance.

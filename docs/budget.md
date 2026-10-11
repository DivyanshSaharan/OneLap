# Durable inference spending reservations

Local development keeps the existing `.data/inference-budget.json` ledger. Hosted
production inference uses `ONELAP_BUDGET_STORAGE=atlas`, because Render's free
filesystem is ephemeral. Offline coverage is supplemented by an
[isolated live counter probe](atlas-budget-verification.md) on October 11.
The production counter was explicitly initialized on October 11 with the preserved
file-ledger floor of **$0.004665 / six requests**. Reopening the Atlas adapter read
back the same reservations; both local spending ledgers remained unchanged. No
provider request or new reservation was made during the import. The exact Render
mission-only overrides are saved and read back. A status preflight against this
production counter passed without constructing a Tinker sampling client; paid
remote sampling remains unverified.

Atlas stores one global OneLap inference counter in the **separate**
`inference_spending` collection, key `onelap:inference:v1`. The collection contains
only integer reservations, an immutable import floor and random request receipts.
It contains no prompts, responses, observations, account IDs or credentials. It
does not share or merge GuardMate or training/evaluation counters. Budget approval
is separate from journal-data sharing: `ONELAP_ATLAS_BUDGET_APPROVED` defaults off.

## Explicit import before enabling production inference

For the approved existing Render service, the immutable import is
`ONELAP_BUDGET_IMPORT_USD=0.004665` and
`ONELAP_BUDGET_IMPORT_REQUESTS=6`, using database `onelap` and the scope above.
The approved cumulative limits are **$0.05 / 20 requests**, including the import,
not $0.05 or 20 additional requests. At initialization, the remaining estimated
reservation allowance is $0.045335 and 14 admissions; actual admissible requests
also depend on each request's token estimate. Mission generation only is approved.
Journal upload, observation/reflection sharing and tracing remain disabled.

The procedure below also applies to a separately approved future migration; do
not reinitialize this production counter or import the floor a second time.

1. Stop model requests and read the current file ledger without modifying it.
2. Set `ONELAP_BUDGET_IMPORT_USD` to its `reserved_microdollars / 1000000` and
   `ONELAP_BUDGET_IMPORT_REQUESTS` to its `reserved_requests`. Both are required.
   The currently known floor is $0.004665 / six requests; read the file again at
   setup time instead of assuming it has not increased. A checked-in release
   minimum also rejects lower imports when Render has no local ledger. This
   minimum is not proof that newer local usage has already been included.
3. Keep the same Atlas database and ledger scope across deployments. Supply the
   existing verified-TLS `MONGODB_URI` server-side. Review and enable the metadata
   storage gate explicitly. No new user account/auth behaviour is implied.
4. Initial creation sets the floor once. Restarts never re-add it. Changing either
   configured floor after creation fails closed rather than merging/resetting the
   counter. A floor below an existing local ledger is rejected.
5. Set an approved cumulative inference budget and request cap; these include the
   imported amounts. Keep all model and text-sharing gates off until approved.

The file remains untouched. Do not delete counters, change databases/scopes or
choose a lower floor to regain allowance. A separately approved migration is
required if legitimate later local usage must be incorporated; no implicit merge
or reset operation is provided.

## Admission and failures

Each actual provider attempt generates a new random receipt. One atomic MongoDB
document update checks both cumulative limits, increments the counters and appends
that receipt. Concurrent processes cannot independently admit requests beyond the
cap. Same-receipt reservation retries do not increment twice; this is storage
idempotency, **not permission to replay a model call**. The application never reuses
a receipt for another sampling attempt and never retries paid sampling.

Primary reads, majority acknowledged writes, bounded connection timeouts and
disabled driver retries are required. Missing/corrupt/mismatched counters, failed
writes, unavailable Atlas or missing approval refuse model sampling. An ambiguous
write is not refunded or silently retried: the stored reservation may remain.
Rejected model output and provider errors keep their reservations. The counter
contains at most 100 receipts under the application's cumulative request limit.

These are conservative token-cost **estimates**, not Tinker's invoice or a guaranteed
provider billing cap. Checkpoint storage, training and evaluation are separate.
They do not establish the account's remaining promotional credit. The approved
October 11 initialization contacted Atlas for the content-free spending counter
only. It did not read journal entries, contact Tinker, export traces or validate
the current remote sampler. No automated paid smoke test is authorized by the
activation approval.

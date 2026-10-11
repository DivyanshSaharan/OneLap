# Isolated Atlas counter check — October 11

The durable counter adapter was exercised against real MongoDB Atlas, using only one temporary content-free collection named `onelap_budget_probe_cf52737d5aa444dc82aeedb1a4cd9672`. The probe injected that collection into the normal adapter; it did not read journal collections, migrate the production counter, enable model requests or change `.env`.

The import floor matched the preserved local ledger: six requests and $0.004665 in estimated reservations. Two artificial one-microdollar admissions tested bookkeeping only; no inference ran or was billed for this probe.

Passed checks:

- The same receipt reserved once even when submitted twice.
- A new adapter instance read the existing counter without re-adding the floor.
- Two concurrent admissions with capacity for only one produced one success and one rejection.
- The exact synthetic counter document was deleted and absence verified. The empty temporary collection may remain; no collection-wide or journal deletion was performed.
- The local inference-ledger file's SHA-256 was unchanged. The production counter was not accessed or modified.

This checks the actual Atlas admission mechanics, not Render deployment, multi-user authorization or provider invoice limits. Production import/activation still needs its explicit configuration gate and stable database scope. See [budget setup](budget.md).

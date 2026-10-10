# Increment 11: repeatable production-browser workflow

Increment 10 was approved, committed and pushed as `07f19e2`. This increment is local and awaits fresh commit/push approval.

## One functionality

A production-browser integration harness runs the real UI and FastAPI routes over exclusively owned loopback HTTP with a disposable browser profile, transient access token and fresh test journal. It verifies mission saving, offline mission/note reload, explicit sync with exact cloud readback, reviewed follow-up acceptance, explicit deletion and offline next-mission reopening. An independent cleanup wrapper deletes only the attempted synthetic entry and verifies empty readback plus replay rejection, including after a lost storage acknowledgment or browser failure.

Default mode is read-only preflight. Fixture mode ignores `.env`, uses labelled local runtime/journal doubles, writes its own isolated fixture ledger and never contacts a provider. Live mode needs both the existing enabled gates/budget and an explicit synthetic-sharing flag. Model attempts are bounded to one mission/one follow-up without automatic retries. The real cumulative ledger is not reset or replaced. Browser subprocesses do not inherit credentials; Sentry is explicitly disabled. Instructions: [browser-smoke.md](browser-smoke.md).

The first actual packaged-server fixture run exposed incorrect Windows registry MIME mappings: JavaScript was served as `text/plain`, preventing module/worker startup. The production static-file handler now explicitly serves the public HTML, JavaScript, CSS, SVG and manifest types. This is a real server fix, not a test-only override. Six regression cases simulate bad OS mappings while preserving `nosniff` and API protection.

## Verification

- A real Edge desktop production-browser run with local services passes all seven stages; zero blocked requests/page errors, two **fixture** samples, verified synthetic deletion/replay rejection.
- 17 new offline backend tests cover isolated owner/data boundaries, tracked lost replies, failed deletion/replay, credential-free children, occupied-port handling, consent/gate enforcement and success/failure cleanup. Six MIME regression tests cover the packaged server.
- Nine Node request-boundary tests reject changed selections, private notes, other owners, extra context, unrelated deletions, repeats, external origins and private paths.
- Full suite passes: 386 backend tests and 158 frontend tests; 24 static-handoff checks and nine browser-boundary checks. Ruff, dependency checks, TypeScript/build/Prettier and the earlier five production browser cases also pass.

No new Tinker, Atlas or Sentry request was made. Saved gates remain off and the real ledger remains four requests / $0.003103 estimated. A fresh live browser run, semantic review, physical-phone offline test and real outing are still pending. Do not use fixture screenshots or synthetic completion as outdoor evidence.

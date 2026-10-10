# Live production-browser evidence — October 10, 2026

**One fresh end-to-end run passed** on commit `f511d52`, using the production desktop interface over protected loopback HTTP, real base `Qwen/Qwen3.5-4B` through Tinker and real MongoDB Atlas. API replies were not intercepted or replaced. This used fictional data, not an actual outing, personal journal or physical phone.

## Approved boundary and result

The user approved up to two additional samples within the existing cumulative $0.05 estimated-spend cap. The fixed input was 15 minutes / generic courtyard / daylight / textures. The single note explicitly said it was fictional: comparing rough and smooth surfaces felt too difficult, with a preference for one texture next time. Feedback was `too_difficult`; no earlier context was selected. `completed` exercised the application gate, not a claim of a completed outing.

| Browser stage | Result | Observed stage time |
| --- | --- | --- |
| Cache public app and connect | Passed | 0.45 s |
| Generate/save a fresh mission | Passed; “Courtyard Texture Hunt” | 12.99 s |
| Reopen offline and save/reopen fictional note | Passed; no automatic upload | 0.48 s |
| Explicit sync and exact Atlas readback | Passed under a fresh journal ID | 1.28 s |
| Review note, generate/accept follow-up | Passed; “Single Surface Notice” | 3.80 s |
| Explicit cloud deletion | Passed | 0.23 s |
| Reopen accepted follow-up offline | Passed without another model request | 0.07 s |

There were exactly two browser model-request attempts, two reserved hosted samples, zero blocked unexpected requests and zero page errors. The independent runner cleanup also deleted the attempted entry, verified an empty active test journal and confirmed that replay returns `journal_entry_deleted`. A content-free deletion tombstone remains; provider backups may retain prior content.

Saved `.env` was unchanged, sharing gates remained off outside the temporary test process, Sentry was disabled, and the test server exited. No personal entries were read. The browser profile was disposable; the normal LAN/static preview was not changed.

## Cost and evidence

This run reserved **$0.001562 estimated**, bringing the preserved cumulative ledger to **six samples / $0.004665 estimated**. The cap stayed $0.05. These figures are local token reservations, not actual invoices or remaining promotional credits. Both newly approved request allowances are used; further inference or training needs fresh approval.

The ignored local report is `.data/browser-smoke/run-xwmzu_ga/report.json`, SHA-256 `14fd6c07142baedc372edbb7ab4cd117728558280e1dd597ec206c5fed4b1f7b`. It preserves exact synthetic replies, timings, source references and cleanup state. Its public frontend index hash is `e1baaf58e76a2e117c5266eddc98067eccc6f4757f91d77b2343b8fb82d5e5c8`. Raw reports/screenshots are not committed or automatically published. The stage timings include UI actions, provider initialization and/or Atlas retrieval; they are not pure inference latency or a matched benchmark.

## Assistant-observed semantic limitations

Both replies retained all four selections, camera false and no phone use during the outing. The follow-up's single-surface task and reflection addressed the fictional difficulty feedback. The application accepted the structured output and rejected neither reply.

This does not establish perfect grounding. Both instructions mention stone, painted walls and wood without knowing those materials exist. The follow-up says to notice one surface but retains the earlier list of alternatives and says “read the list,” rather than producing an especially clean one-action instruction. Its reflection adds a vague reassurance (“You did what you needed to do”) unsupported by the observation. These are assistant observations, not a completed human rubric or model-accuracy score.

The run did not test semantic quality across a dataset, fine-tuning, actual outdoor usefulness, a physical phone, installation, public deployment or Sentry ingestion. The saved-source-reference feature added after this run is verified separately with local browser fixtures; it was not the subject of these two hosted requests.

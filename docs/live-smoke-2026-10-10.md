# Live integration evidence — October 10, 2026

This is an integration check with fictional data, not an outdoor test, a training comparison or a model-accuracy measurement. The model was base `Qwen/Qwen3.5-4B` through Tinker. No OneLap adapter has been trained.

## Approved boundary

The request was 15 minutes, a generic courtyard, evening conditions and textures. The observation was explicitly labelled fictional: rough and smooth surfaces were noticed, with a preference for a gentler next task. No personal journal entries, precise locations, photographs or audio were used.

The user approved one mission and one follow-up under a $0.05 model cap, then two additional requests after the first mission was rejected. Three hosted samples were actually used: two mission attempts and one follow-up. Saved approval gates remained off; subprocess overrides enabled only the approved run. The spend ledger was preserved across failures and resumption.

## Results

| Stage | Observed result |
| --- | --- |
| First mission | Rejected as `invalid_model_output`; no Atlas upload attempted. Its raw reply was not captured, so the exact parsing/schema defect is unknown. |
| Second mission | Passed application validation. The later Atlas attempt failed due to sandbox SRV DNS resolution; a read-only check outside the sandbox confirmed that entry was absent. |
| Resumed test | Reused the second mission and its matching captured reply, without generating another mission. |
| Atlas upload and duplicate upload | Passed; one exact entry was read back. |
| Other-owner request | Rejected as expected. This checks the single-journal owner boundary, not multi-user authentication. |
| Follow-up | Reached Qwen and returned parseable structured output, but changed focus from `textures` to `light`; rejected as `mission_constraint_mismatch`. |
| Cleanup | Deleted test content, verified an empty test journal and rejected replay of the deleted entry. A content-free tombstone remains. |

The successful Atlas run used an in-process FastAPI client with real external Tinker/Atlas services, outside the sandbox to resolve Atlas DNS. This is not a browser, phone or deployment test. The whole run remained marked failed because the follow-up was rejected.

## Time and reservation observations

The two mission stages took about 19.85 seconds and 13.07 seconds; the first included cold tokenizer setup. The follow-up stage took about 12.02 seconds. These are single observed end-to-end API-stage timings, not isolated inference latency or a performance benchmark.

In the resumed run, Atlas upload took about 944 ms, duplicate upload 35 ms, exact readback 29 ms, owner rejection 2 ms and combined deletion/readback/replay checking 85 ms. These are one-run observations, not database service guarantees.

Local estimated reservations were $0.000737, $0.000737 and $0.000804, totalling **$0.002278**. Reservations are conservative local bookkeeping, not provider invoices or proof of remaining promotional credit.

## What this changed

Raw replies for the fixed synthetic workflow are now captured before parsing, so later rejected output is inspectable without requesting another sample. Reports remain ignored locally; secrets and raw SDK/database exceptions are not included.

The follow-up prompt was revised to `follow-up-v2`: its supplied schema gives minutes, setting, conditions and focus exact constant values, and the instructions explain how to make a texture task gentler without switching focus. Application validation still rejects changed constraints. Regression tests cover this boundary; old saved prompt versions remain readable. **The revised prompt has not been sampled live.**

The accepted mission also illustrates why schema validity is not usefulness: it referred to night, lamps/moonlight, walls, steps and railings that were not supplied, and leaned towards light/shadows rather than a concrete texture activity. Those issues require semantic review; accepting its schema is not an endorsement of its quality or safety.

No successful accepted live follow-up, measured accuracy, fine-tuning improvement, physical-phone installation, public deployment or real outdoor result is claimed. The next hosted check needs new request approval.

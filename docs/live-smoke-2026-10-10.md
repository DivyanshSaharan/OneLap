# Live integration evidence — October 10, 2026

This is an integration check with fictional data, not an outdoor test, a training comparison or a model-accuracy measurement. The model was base `Qwen/Qwen3.5-4B` through Tinker. No OneLap adapter has been trained.

## Approved boundary

The request was 15 minutes, a generic courtyard, evening conditions and textures. The observation was explicitly labelled fictional: rough and smooth surfaces were noticed, with a preference for a gentler next task. No personal journal entries, precise locations, photographs or audio were used.

The user approved one mission and one follow-up under a $0.05 model cap, then two additional requests after the first mission was rejected, and finally one follow-up-only retest of the revised prompt. Four hosted samples were actually used: two mission attempts and two follow-ups. Saved approval gates remained off; subprocess overrides enabled only each approved run. The spend ledger was preserved across failures and resumption. All four request allowances are now used.

## Results

| Stage | Observed result |
| --- | --- |
| First mission | Rejected as `invalid_model_output`; no Atlas upload attempted. Its raw reply was not captured, so the exact parsing/schema defect is unknown. |
| Second mission | Passed application validation. The later Atlas attempt failed due to sandbox SRV DNS resolution; a read-only check outside the sandbox confirmed that entry was absent. |
| Resumed test | Reused the second mission and its matching captured reply, without generating another mission. |
| Atlas upload and duplicate upload | Passed; one exact entry was read back. |
| Other-owner request | Rejected as expected. This checks the single-journal owner boundary, not multi-user authentication. |
| Initial follow-up | Reached Qwen and returned parseable structured output, but changed focus from `textures` to `light`; rejected as `mission_constraint_mismatch`. |
| Revised-prompt retest | Reused the captured mission, created a new isolated test entry and accepted one live `follow-up-v2` with all four selected fields preserved. No new mission was sampled. |
| Cleanup | Deleted test content, verified an empty test journal and rejected replay of the deleted entry. A content-free tombstone remains. |

Both resumed Atlas runs used an in-process FastAPI client with real external Tinker/Atlas services, outside the sandbox to resolve Atlas DNS. The earlier run remained failed because its follow-up was rejected; the revised-prompt retest passed all workflow checks, including deletion and replay rejection. This is not a fresh two-generation run, browser, phone or deployment test. Neither run read the personal journal.

## Time and reservation observations

The two mission stages took about 19.85 seconds and 13.07 seconds; the first included cold tokenizer setup. The initial follow-up stage took about 12.02 seconds; the accepted retest took about 14.75 seconds. These are single observed API-stage timings, including retrieval/setup where applicable, not isolated inference latency or a matched performance benchmark.

In the resumed run, Atlas upload took about 944 ms, duplicate upload 35 ms, exact readback 29 ms, owner rejection 2 ms and combined deletion/readback/replay checking 85 ms. These are one-run observations, not database service guarantees.

Local estimated reservations were $0.000737, $0.000737, $0.000804 and $0.000825, totalling **$0.003103** across four samples. The cumulative $0.05 cap was not raised. Reservations are conservative local bookkeeping, not provider invoices or proof of remaining promotional credit.

## What this changed

Raw replies for the fixed synthetic workflow are now captured before parsing, so later rejected output is inspectable without requesting another sample. Reports remain ignored locally; secrets and raw SDK/database exceptions are not included.

The follow-up prompt was revised to `follow-up-v2`: its supplied schema gives minutes, setting, conditions and focus exact constant values, and the instructions explain how to make a texture task gentler without switching focus. Application validation still rejects changed constraints. Regression tests cover this boundary; old saved prompt versions remain readable. **One separately approved live retest now passed these application checks.** This is supplied-schema prompting, not constrained decoding or a trained adapter.

The accepted mission also illustrates why schema validity is not usefulness: it referred to night, lamps/moonlight, walls, steps and railings that were not supplied, and leaned towards light/shadows rather than a concrete texture activity. Those issues require semantic review; accepting its schema is not an endorsement of its quality or safety.

## Accepted follow-up and remaining semantic weaknesses

The accepted result proposed attending to one surface rather than comparing two. It retained 15 minutes/courtyard/evening/textures, camera false and no phone use, and did not exactly repeat the prior instruction. Its reflection referred to the rough/smooth comparison and preference for something gentler.

It still called evening "night," assumed steps/walls exist, concentrated on light/shadows rather than a distinct texture task, and used "You chose" in the remember field before the user had accepted the suggestion. The reflection also added "quiet" surroundings not reported by the user. These are assistant-observed limitations, **not a completed human rubric review**. The original observation's text said comparison was easy while its feedback flag was `too_difficult`; that inconsistency also limits conclusions about adaptation.

The public [captured mission example](../examples/captured-followup-2026-10-10.json) is unmodified and was locally compared with the accepted response. The raw synthetic report stays ignored at `.data/smoke/5defc597-b832-4bd4-9006-764be0772d9e.json`, SHA-256 `30500748426225eeb50f0a9ff87f3b1a3b8866e365d011af66901a3231d7946f`. Cleanup was verified; only a content-free deletion tombstone remains. Tracing was disabled for the retest.

One accepted revised follow-up and a successful resumed API workflow are now evidenced. No measured accuracy, held-out evaluation, fine-tuning improvement, physical-phone installation, public deployment or real outdoor result is claimed. Further hosted requests and training still require new approval.

# Phone, outdoor and demo handoff

These are **instructions and an unfilled checklist**, not field results. The local mission import lets the captured result be used without another hosted request. All saved sharing/spending gates remain off. Training still needs reviewed data and an approved budget.

## First phone check

1. Follow [the private Android setup](phone-setup.md): build (`npm.cmd run build`), run the API-free static handoff (`npm.cmd run handoff`), and map only loopback port 4176 over USB. Ordinary laptop LAN HTTP is not enough for service-worker offline caching. No backend, public tunnel or paid generation is needed. Physical-phone success remains unverified.
2. Download only the public captured mission from the connected handoff guide. Do not transfer `.env`, the full smoke report, credentials or the spend ledger.
3. Open OneLap, expand **Use a captured mission · no model request**, choose the file and read the preview. If unsuitable, discard it. The example has documented semantic weaknesses, not a guarantee about your surroundings.
4. If you want it, check the review box and save. Verify the imported/unverified label and **Saved on this device · ready to reopen offline**. If the app shell is not ready, do not claim offline readiness.
5. Disconnect networking, reload the page and verify the mission and provenance label remain. Enter pocket mode; confirm the preparation/import controls disappear. Record a harmless local test note after returning and reload again. Do not sync real notes without separately reviewing the sharing boundary.

The desktop Edge test passed these import/reload steps with a labelled fixture and no private API calls, at 320/390/1280-pixel widths. That is not a physical-phone result. Installation prompts remain unverified. The app starts no outing timer, GPS tracking or automatic completion record.

## Two small outings

Use a familiar area you choose; no particular landmark is needed. Start only if the task and conditions suit you, and skip or stop if they do not. Do not invent results to fill the table. If using the captured response, describe it as a previously generated synthetic-test mission, not a fresh live request. A new personalized mission/reflection requires separately approved data sharing and model spending.

Read once, put the phone away, then write the observation after returning. No screenshot/photo is required outdoors. If you choose to record duration or phone interactions, measure or self-report them separately; the app cannot know how often you used other apps or whether you actually went outside.

| Evidence | Outing A | Outing B |
| --- | --- | --- |
| Actual date, without precise location | Pending | Pending |
| Mission ID/source and selected minutes | Pending | Pending |
| Preparation time and measurement method | Pending | Pending |
| Completed, stopped or skipped | Pending | Pending |
| Outdoor duration, with method or "not measured" | Pending | Pending |
| Phone interactions, with method or "not measured" | Pending | Pending |
| One real observation, without identifying details | Pending | Pending |
| Suitability and specific failure/awkward wording | Pending | Pending |
| Did the mission need changing, and why? | Pending | Pending |
| Reflection grounded in the real note, if separately tested | Pending | Pending |

Keep raw notes private until reviewed. Exact places, addresses, office details, identifiable faces/signs, notification content and credentials do not belong in the public demo. A two-outing personal test is not proof of broad behavior change or an accuracy benchmark.

## Short honest demo

- Explain the full work-and-commute day and why a small outing is achievable; omit identifiable locations.
- Show selections and the explicit hosted-data boundary. Do not click generation without an approved request allowance.
- Show local import of the captured base-model response, review-before-save, its unverified label and the documented failure/quality limits. This is playback of an earlier result, not live inference.
- Demonstrate pocket mode, disconnected reload and local observation capture. A desktop phone-width recording must be labelled as such; do not call it a phone/outdoor test.
- Link the actual Atlas/Tinker integration evidence separately. Local import proves neither cloud synchronization nor live follow-up.
- Add real outing feedback only after it exists. Review the recording before public sharing; do not publish automatically.

[The reproducible local recorder](demo.md) demonstrates this UI loop in a new desktop context, with visible capture-playback disclosures and a fictional skipped outing. Its video stays ignored and local until reviewed and approved for upload. [The DEV draft](submission-draft.md) still needs a real public video URL and truthful field-test update.

## Submission boundary

The [official challenge page](https://dev.to/challenges/hacktoberfest-week1-2026-10-05), checked October 10, specifies October 11 at 11:59 PM PDT (October 12 at 12:29 PM IST). Keep October 11 as the internal target. Required tags are `devchallenge` and `hf26challenge`; use the supplied DEV template. Post-deadline commits must be noted in the README.

Atlas is actually used in the verified workflow. Tinker inference is demonstrated, but its category requires fine-tuning plus a baseline improvement; neither exists yet. Render packaging and local Sentry SDK tests are not deployment/dashboard evidence. List only genuinely demonstrated categories, following [the category criteria](https://dev.to/challenges/hacktoberfest-week1-2026-10-05). Demo video, human review, phone checks, outdoor feedback and any optional agent-session export remain pending. Nothing has been posted or deployed by this increment.

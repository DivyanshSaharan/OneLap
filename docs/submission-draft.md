---
title: "OneLap: after work, before scrolling"
published: false
tags: devchallenge, hf26challenge, ai, mongodb
---

<!-- DRAFT: Add the reviewed public video URL. Update the field-test paragraph only after tomorrow's actual outing. Check every claim against the submitted commit; remove this comment before publishing. -->

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).*

## What I Built

By the time work and commuting are done, the stretch from 7 AM to 7 PM is already spoken for. A big adventure is not always realistic. Fifteen minutes outside might be.

I built **OneLap** for that gap: after work, before scrolling.

Choose a small time window, a familiar outdoor setting and something to notice. OneLap uses an open-weight model to create a short observation mission. Read it, put the phone away, and bring back one thought. After returning, you can save an observation and, with separate sharing approval, ask for a reflection and an adapted next mission.

It is not a route planner, a fitness tracker or a chatbot to keep open while walking. There is no GPS permission, compulsory photo, timer, streak or feed. An outing can be completed, stopped or skipped; the app does not pretend to verify any of those.

The interesting AI problem is not generating a list of outdoor activities. It is turning limited time and a person's feedback into one small, suitable task, without inventing their surroundings or adding more screen work.

**Field check:** the physical-phone and outdoor test is still pending. I have not yet demonstrated that OneLap changes how often I go outside. I will report the actual result, including awkward wording or a failed offline reload, rather than substitute a simulated outing.

## Demo

**Video:** reviewed public link pending. There is no public deployment.

The locally recorded walkthrough shows the real interface at phone width: review a previously captured Qwen response, save it, use pocket mode, reload with browser networking disabled, and save/reopen a fictional local note. The recording labels itself as **desktop capture playback**, not live inference or a physical-phone test. Its fictional outing is marked skipped, not completed.

The capture is unmodified and came from an earlier synthetic integration test. Imported files remain labelled **model provenance not verified**. [Capture provenance and quality caveats](https://github.com/DivyanshSaharan/OneLap/blob/main/examples/README.md) and [the separate real-service test evidence](https://github.com/DivyanshSaharan/OneLap/blob/main/docs/live-smoke-2026-10-10.md) are in the repository.

A separate fresh production-browser run also passed using real Qwen/Tinker and Atlas: generate a mission, save a fictional note offline, sync it, review and request a follow-up, delete the note, and reopen the next mission offline. [Its evidence](https://github.com/DivyanshSaharan/OneLap/blob/main/docs/live-browser-2026-10-10.md) is separate from the playback video; neither is an outdoor test.

## Code

{% github https://github.com/DivyanshSaharan/OneLap %}

The repository includes the application, application checks, tests, synthetic evaluation inputs, captured example and build plan. Credentials, journal data, raw test reports and spend bookkeeping are not committed.

## How I Built It

The AI core is **[Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)**, sampled and fine-tuned through Tinker's Python SDK. I completed one rank-16 LoRA candidate: 100 synthetic supervised examples, three epochs and 30 updates. The app still defaults to the base model; a completed training job does not silently activate its adapter.

The application is React and TypeScript on the phone side, with FastAPI and Pydantic on the backend. A service worker caches the public app shell. IndexedDB holds the saved mission and local observation outbox. MongoDB Atlas stores explicitly synchronized journal entries and provides the selected notes for follow-ups.

The workflow has two different boundaries:

- **Before leaving:** generic selections go to hosted Qwen; the app validates its structured response before presenting it.
- **After returning:** observations save locally first. Atlas synchronization is explicit. A follow-up separately reviews selected notes, asks for sharing consent, and has the server retrieve only those records for Qwen.

Generation and new reflections require connectivity and hosted inference. Reading a previously downloaded mission and saving a local note can work without it. This is **not an offline-inference claim**.

I also kept application restrictions outside the model: bounded requests, conservative spend reservations, no automatic inference retries, and checks that a follow-up preserves the selected duration, setting, conditions and focus. A model's confident wording is not a safety assessment.

One failure mattered: an early follow-up changed the requested focus and the app rejected it. After revising the prompt, an approved retest preserved all four selections and passed the resumed Tinker/Atlas workflow, including deleting the isolated test note and rejecting replay.

That did not make the output perfect. The accepted mission still assumed night and particular objects, leaned on shadows, and described a proposed choice as already made. I kept those defects in the capture and documentation. Valid JSON and passing constraints are not the same as a grounded, useful outing.

Two additional approved samples then passed a fresh hosted production-browser loop. The reflection addressed the fictional difficulty feedback and proposed noticing one surface instead of comparing two. The new text still named materials it did not know were present, and reused “read the list” wording. Both replies passed application checks; that is not perfect semantic grounding.

There have been six hosted samples in these small synthetic integration checks, not an accuracy benchmark. Offline unit/browser tests cover state, storage, validation and sharing boundaries; they do not measure whether the missions are enjoyable. Accepted follow-ups now preserve local source references without copying the notes or automatically fetching them; that newer local feature was tested with fixtures after the live run.

I then froze a separate synthetic corpus and ran a matched baseline-versus-adapter pilot. Families were split before creating five variants each: 100 training targets, 20 development inputs and 30 held-out inputs. The targets are assistant-authored and agent-reviewed, not human-reviewed outings. Both models used the same prompts, checks and decoding, with one sample per input and no held-out-driven iteration.

| Passing the application's checks | Base Qwen | LoRA candidate |
| --- | --- | --- |
| Development | 16/20 (80%) | 20/20 (100%) |
| Held-out | 20/30 (66.7%) | 29/30 (96.7%) |

The held-out gain is **30 percentage points in application acceptance**, not a claim of 96.7% semantic accuracy. The variants are correlated, the set is small, and independent human review is pending. One adapter reply still failed: the keyword filter rejected “without recording it,” because it does not understand negation. I left that failure in the result and did not change the check after seeing it.

The pilot reserved $0.285662 for training and 100 evaluation samples under a separate $0.75 token allowance; this is not an invoice total and excludes checkpoint storage. Only the final sampler was saved, with a seven-day expiry. [Full method, failures, latency and cost limitations](https://github.com/DivyanshSaharan/OneLap/blob/main/docs/pilot-results.md) and [hash-bound public metrics](https://github.com/DivyanshSaharan/OneLap/blob/main/reports/onelap-pilot-v1.json) are available. No automatic model promotion or broader quality claim follows from those numbers.

## Why Does Open Innovation Matter?

A closed text-generation API could produce an outdoor prompt too. What matters to me is control over the small behavior this project needs: concise tasks, grounded reflections, feedback-sensitive adaptation and less phone interaction.

With an open-weight model, I can adapt the model's behavior rather than only rewrite a general-purpose prompt. OneLap's pilot turned that option into an actual experiment: task-specific supervision improved the rate of responses the unchanged application could accept. The repository freezes exact prompts and replays captured replies through the same checks. That control does not remove the need for human review, but it lets me investigate a failure at the model level and measure a narrowly defined improvement.

Separating the provider from the application's rules also leaves a path to another compatible model/runtime. That portability is an architectural option, not a verified local deployment today. The present Qwen requests run on Tinker, so shared text still leaves the device; open weights alone do not provide privacy or free inference.

The privacy benefit I can demonstrate now comes from the application design: no location collection, local-first notes, explicit sharing and no background analysis. The screen-light benefit is the intended experience: AI helps prepare a small outing, then gets out of the way.

## Prize Categories

**Best Use of MongoDB Atlas** — Atlas is the persistent journal behind the open-weight-model workflow. Selected stored observations become the context for an explicitly approved follow-up. Isolated live tests verified storage, duplicate prevention, owner-scoped reads and deletion/replay behavior.

**Best Use of Tinker** — one task-specific Qwen LoRA candidate, matched baseline/adapter captures and a measured held-out application-acceptance improvement from 20/30 to 29/30. The method and limitations above distinguish that result from semantic accuracy or field usefulness.

Render packaging and local Sentry instrumentation are not claims of a deployed service or a live tracing dashboard. Those categories remain unclaimed until actually demonstrated.

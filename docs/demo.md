# Reproducible, no-spend walkthrough

The recorder uses a fresh disposable desktop browser at 480 × 960 pixels, not your existing tabs or journal. It downloads the public synthetic capture, checks its bytes, imports it through the real UI, tests review gating and saved provenance, enters pocket mode, disables browser networking, reloads the mission, and saves/reloads a clearly fictional local note with outcome **skipped**. It also checks that the guide/download still work after the service worker controls the app.

No backend runs. The static server has no API proxy or SDK clients, and the browser blocks unexpected origins/private API calls. The recording contains no live generation, Atlas sync, new reflection, trained adapter, physical phone or outing. Its overlay states these boundaries; it changes only the recording presentation, not application values or model text. [The real API evidence](live-smoke-2026-10-10.md) is a separate synthetic resumed workflow.

## Record locally

Use the existing dependencies and installed Edge. From the project directory, install the optional recorder binary into the project's ignored cache once:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.data/playwright-browsers'
npx.cmd playwright install ffmpeg
$env:ONELAP_TEST_BROWSER = 'msedge'
npm.cmd run build
npm.cmd run demo
```

The recorder defaults to that same project-local dependency cache. Without the Edge setting, install Playwright Chromium into the selected cache first. These are browser/recorder dependencies, not downloads of remote media or model weights. Video recording follows [Playwright's video API](https://playwright.dev/docs/videos).

Each run gets a fresh `.data/demo/run-*` directory. It contains `OneLap-demo.webm`, three checkpoint screenshots, public JSON downloads and a manifest with capture/public-file/video hashes, stage names and request/error counts. Output is ignored, not staged or uploaded. The manifest must say **passed** with zero private API attempts, blocked requests and page errors. A failed run is labelled **failed_do_not_publish**; keep partial artifacts separate from a successful recording.

The script closes its browser/server. It never changes saved approval gates, reads secrets, spends model credit or accesses a real journal. A matching capture hash supports exact playback, not proof that every imported file is genuine model output. The unverified label remains in the app.

## Before sharing

Watch the full successful clip, not only the screenshots. Ensure the disclosure overlay is readable, the full mission/known defects remain, and the fictional note is not mistaken for outdoor evidence. Keep the original WebM; convert a copy locally if your chosen host needs MP4. Review any conversion too.

Only upload with the user's explicit approval, then add the actual public video URL to the README and [DEV draft](submission-draft.md). Do not link an ignored local path as though it were a public demo. Public hosting/publication is not performed by this command.

Tomorrow's real phone check and outdoor feedback belong in [field-test.md](field-test.md). This recording is useful UI evidence, not a replacement for those results or an accuracy benchmark.

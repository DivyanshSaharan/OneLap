import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { capturePath, projectRoot, startHandoff } from './static-handoff.mjs'

// Resolve the optional recorder in this project's ignored dependency cache.
process.env.PLAYWRIGHT_BROWSERS_PATH ??= join(
  projectRoot,
  '.data/playwright-browsers',
)
const { chromium, expect } = await import('@playwright/test')

const captionId = 'onelap-demo-caption'
const observation =
  'Fictional demo note — no outing took place. I noticed a rough surface beside a smooth one.'
const stages = []

async function caption(page, title, detail) {
  // Recording-only overlay; no application fields or model replies are altered.
  await page.evaluate(
    ({ id, title, detail }) => {
      let banner = document.getElementById(id)
      if (!banner) {
        banner = document.createElement('aside')
        banner.id = id
        banner.setAttribute('aria-label', 'Recording disclosure')
        Object.assign(banner.style, {
          position: 'fixed',
          top: '0',
          left: '0',
          right: '0',
          zIndex: '9999',
          padding: '12px 18px',
          background: '#193c2d',
          color: '#fffef5',
          font: '13px/1.5 system-ui,sans-serif',
          boxShadow: '0 2px 8px #0003',
        })
        document.body.append(banner)
        document.body.style.paddingTop = '100px'
      }
      banner.replaceChildren()
      const disclosure = document.createElement('div')
      disclosure.textContent =
        'DESKTOP DEMO · Captured base Qwen · No live API calls'
      const heading = document.createElement('strong')
      heading.textContent = title
      const description = document.createElement('div')
      description.textContent = detail
      banner.append(disclosure, heading, description)
    },
    { id: captionId, title, detail },
  )
  stages.push(title)
}

async function main() {
  if (process.argv.length !== 2) throw new Error('unsupported_arguments')
  const channel = process.env.ONELAP_TEST_BROWSER
  if (channel && channel !== 'msedge') throw new Error('unsupported_browser')
  const root = join(projectRoot, '.data/demo')
  await mkdir(root, { recursive: true })
  const output = await mkdtemp(join(root, 'run-'))
  let preview
  let browser
  let context
  let video
  let passed = false
  const errors = []
  const blocked = []
  const capture = await readFile(capturePath)
  const capturedMission = JSON.parse(capture.toString('utf8'))
  try {
    preview = await startHandoff({ port: 0 })
    browser = await chromium.launch({
      ...(channel ? { channel } : {}),
      headless: true,
    })
    context = await browser.newContext({
      viewport: { width: 480, height: 960 },
      serviceWorkers: 'allow',
      reducedMotion: 'reduce',
      recordVideo: { dir: output, size: { width: 480, height: 960 } },
    })
    await context.route('**/*', async (route) => {
      const url = new URL(route.request().url())
      if (url.origin !== preview.origin || url.pathname.startsWith('/api/')) {
        blocked.push(url.pathname)
        await route.abort()
      } else await route.continue()
    })
    const page = await context.newPage()
    page.setDefaultTimeout(15000)
    page.on('pageerror', () => errors.push('page_error'))
    video = page.video()
    await page.goto(`${preview.origin}/handoff`)
    await caption(
      page,
      'Private setup, no spend.',
      'Static files only. This recorder uses a new, empty browser context.',
    )
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page
        .getByRole('link', { name: 'Download the captured mission JSON' })
        .click(),
    ])
    const downloadedFile = join(output, 'captured-mission.json')
    await download.saveAs(downloadedFile)
    assert.deepEqual(await readFile(downloadedFile), capture)
    await page.waitForTimeout(3000)
    await page.getByRole('link', { name: 'Open OneLap' }).click()
    await caption(
      page,
      'After work, before scrolling.',
      'Phone-width browser recording, not a physical-phone or outdoor test.',
    )
    await expect(
      page.getByRole('heading', { name: 'Your outing starts here.' }),
    ).toBeVisible()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.waitForTimeout(4000)
    await page.waitForFunction(() =>
      Boolean(navigator.serviceWorker.controller),
    )
    // A cached app must not replace the guide/download with an app-shell reply.
    await page.goto(`${preview.origin}/handoff`)
    await expect(
      page.getByRole('heading', { name: 'Read once. Then step outside.' }),
    ).toBeVisible()
    const [cachedDownload] = await Promise.all([
      page.waitForEvent('download'),
      page
        .getByRole('link', { name: 'Download the captured mission JSON' })
        .click(),
    ])
    const cachedDownloadFile = join(output, 'captured-mission-after-cache.json')
    await cachedDownload.saveAs(cachedDownloadFile)
    assert.deepEqual(await readFile(cachedDownloadFile), capture)
    await page.getByRole('link', { name: 'Open OneLap' }).click()
    await expect(page.getByLabel('Mission JSON file')).toBeEnabled()
    await page
      .getByText('Use a captured mission · no model request', { exact: true })
      .click()
    await page.getByLabel('Mission JSON file').setInputFiles(downloadedFile)
    await expect(page.getByText('FILE PREVIEW · NOT YET SAVED')).toBeVisible()
    await caption(
      page,
      'Review the earlier captured response.',
      'No new generation. The original wording and known defects are kept.',
    )
    await page.locator('.import-preview').scrollIntoViewIfNeeded()
    await expect(
      page.getByRole('button', { name: 'Save imported mission' }),
    ).toBeDisabled()
    await page.waitForTimeout(4000)
    await page
      .getByRole('checkbox', { name: /I reviewed this unverified file/ })
      .check()
    await page.getByRole('button', { name: 'Save imported mission' }).click()
    const heading = page.getByRole('heading', {
      name: capturedMission.mission.title,
      exact: true,
    })
    await expect(heading).toBeVisible()
    await expect(
      page.getByText('Saved on this device · ready to reopen offline'),
    ).toBeVisible()
    await expect(
      page.getByText('Imported file · model provenance not verified'),
    ).toBeVisible()
    await caption(
      page,
      'One mission, saved locally.',
      'Base Qwen through Tinker was used earlier; this recording is capture playback.',
    )
    await heading.scrollIntoViewIfNeeded()
    await page.waitForTimeout(4000)
    await page.screenshot({ path: join(output, '01-captured-mission.png') })
    await page.getByRole('button', { name: /I’m heading out/ }).click()
    await caption(
      page,
      'Read once. Pocket the phone.',
      'No GPS, camera, timer or automatically reported completion.',
    )
    await heading.scrollIntoViewIfNeeded()
    await page.waitForTimeout(4000)
    await page.locator('.pocket-footer').scrollIntoViewIfNeeded()
    await page.waitForTimeout(3000)
    await context.setOffline(true)
    await page.reload()
    await expect(heading).toBeVisible()
    await expect(page.getByText('Device offline')).toBeVisible()
    await expect(
      page.getByText('Imported file · model provenance not verified'),
    ).toBeVisible()
    await caption(
      page,
      'Reload with browser networking disabled.',
      'The downloaded app and saved mission reopen. Generation still needs connectivity.',
    )
    await heading.scrollIntoViewIfNeeded()
    await page.waitForTimeout(4000)
    await page.screenshot({ path: join(output, '02-offline-reload.png') })
    await page.getByRole('button', { name: /I’m heading out/ }).click()
    await page
      .getByRole('button', { name: 'I’m back — record an observation' })
      .click()
    await page.getByLabel('How did the outing go?').selectOption('skipped')
    await page.getByLabel('What did you notice?').fill(observation)
    await caption(
      page,
      'Save a fictional note after returning.',
      'This demo marks the outing skipped. No real-world completion or feedback is claimed.',
    )
    await page.getByLabel('What did you notice?').scrollIntoViewIfNeeded()
    await page.waitForTimeout(4000)
    await page
      .getByRole('button', { name: 'Save observation on this device' })
      .click()
    await expect(
      page.getByText(
        'Observation saved on this device. Not uploaded, and not sent to AI.',
      ),
    ).toBeVisible()
    await page.reload()
    await expect(page.getByText(observation, { exact: true })).toBeVisible()
    await caption(
      page,
      'The local note survives offline reload.',
      'No Atlas sync or new AI reflection is shown. Physical-phone and outdoor checks are next.',
    )
    await page.locator('.journal-entry').scrollIntoViewIfNeeded()
    await page.waitForTimeout(4000)
    await page.screenshot({ path: join(output, '03-local-note.png') })
    await caption(
      page,
      'A small break, not another feed.',
      'Open-weight AI at the planning step; the outing itself should be screen-light.',
    )
    await page.waitForTimeout(3000)
    assert.deepEqual(blocked, [])
    assert.deepEqual(preview.apiAttempts, [])
    assert.deepEqual(errors, [])
    passed = true
  } finally {
    try {
      await context?.close()
      if (passed) await video.saveAs(join(output, 'OneLap-demo.webm'))
    } catch {
      passed = false
      errors.push('video_finalize_failed')
    } finally {
      try {
        await browser?.close()
      } finally {
        await preview?.close()
      }
    }
    const manifest = {
      version: 1,
      status: passed ? 'passed' : 'failed_do_not_publish',
      mode: 'desktop_phone_width_captured_playback',
      physical_phone_test: false,
      outdoor_test: false,
      live_inference: false,
      cloud_sync: false,
      synthetic_note_outcome: 'skipped',
      capture_sha256: createHash('sha256').update(capture).digest('hex'),
      public_files_sha256: preview?.publicFilesSha256 ?? null,
      private_api_attempt_count: preview?.apiAttempts.length ?? null,
      blocked_request_count: blocked.length,
      page_error_count: errors.length,
      stages,
      publication: 'local_only_requires_user_review_and_approval',
    }
    if (passed)
      manifest.video_sha256 = createHash('sha256')
        .update(await readFile(join(output, 'OneLap-demo.webm')))
        .digest('hex')
    await writeFile(
      join(output, 'manifest.json'),
      `${JSON.stringify(manifest, null, 2)}\n`,
      { flag: 'wx' },
    )
  }
  if (!passed) throw new Error('demo_failed')
  process.stdout.write(
    `Demo checks passed. Review before publishing:\n${join(output, 'OneLap-demo.webm')}\n${join(output, 'manifest.json')}\n`,
  )
}

try {
  await main()
} catch {
  process.stderr.write(
    'Demo recording failed; do not publish partial artifacts. Check the build, browser and Playwright recorder installation.\n',
  )
  process.exitCode = 1
}

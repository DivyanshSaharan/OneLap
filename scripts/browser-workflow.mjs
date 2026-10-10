import assert from 'node:assert/strict'
import { writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const origin = 'http://127.0.0.1:8770'

export class RequestBoundary {
  constructor(input) {
    assert.equal(input.origin, origin)
    this.input = input
    this.modelAttempts = 0
    this.missions = 0
    this.followups = 0
    this.uploads = 0
    this.deletes = 0
    this.entry = null
  }

  admit(urlString, method, headers, body) {
    const url = new URL(urlString)
    assert.equal(url.origin, origin)
    assert.equal(url.search, '')
    if (!url.pathname.startsWith('/api/')) {
      assert.equal(method, 'GET')
      assert.match(
        url.pathname,
        /^(?:\/(?:index\.html|sw\.js|icon\.svg|manifest\.webmanifest)?|\/assets\/[\w.-]+\.(?:js|css))$/,
      )
      return
    }
    assert.equal(headers.authorization, `Bearer ${this.input.token}`)
    if (method === 'GET') {
      assert.ok(
        [
          '/api/model/status',
          '/api/journal/status',
          '/api/journal/entries',
          '/api/followups/status',
        ].includes(url.pathname),
      )
      if (url.pathname.endsWith('/entries'))
        assert.equal(headers['x-onelap-journal-owner'], this.input.owner)
    } else if (method === 'POST' && url.pathname === '/api/missions') {
      assert.equal(this.missions++, 0)
      assert.deepEqual(body, this.input.request)
      this.modelAttempts++
    } else if (method === 'POST' && url.pathname === '/api/journal/entries') {
      assert.equal(this.uploads++, 0)
      assert.deepEqual(Object.keys(body).sort(), ['entry', 'owner_id'])
      assert.equal(body.owner_id, this.input.owner)
      assert.equal(body.entry.observation, this.input.observation)
      assert.equal(body.entry.outcome, 'completed')
      assert.equal(body.entry.feedback, 'too_difficult')
      assert.match(body.entry.id, /^[0-9a-f-]{36}$/)
      this.entry = body.entry
    } else if (method === 'POST' && url.pathname === '/api/followups') {
      assert.equal(this.followups++, 0)
      assert.ok(this.entry)
      assert.equal(headers['x-onelap-journal-owner'], this.input.owner)
      assert.deepEqual(body, { source_id: this.entry.id, context_ids: [] })
      this.modelAttempts++
    } else if (method === 'DELETE') {
      assert.ok(this.entry)
      assert.equal(this.deletes++, 0)
      assert.equal(url.pathname, `/api/journal/entries/${this.entry.id}`)
      assert.equal(headers['x-onelap-journal-owner'], this.input.owner)
      assert.equal(body, null)
    } else throw new Error('unexpected_browser_request')
  }
}

async function main() {
  if (process.argv.length !== 2) throw new Error('unsupported_arguments')
  let stdin = ''
  for await (const chunk of process.stdin) {
    stdin += chunk
    if (stdin.length > 8192) throw new Error('oversized_configuration')
  }
  const input = JSON.parse(stdin)
  const output = resolve(input.output)
  const outputRelative = relative(join(root, '.data/browser-smoke'), output)
  assert.match(outputRelative, /^run-[\w-]+$/)
  assert.ok(!outputRelative.includes(sep))
  const boundary = new RequestBoundary(input)
  process.env.PLAYWRIGHT_BROWSERS_PATH ??= join(
    root,
    '.data/playwright-browsers',
  )
  const { chromium, expect } = await import('@playwright/test')
  const channel = process.env.ONELAP_TEST_BROWSER
  assert.ok(!channel || channel === 'msedge')
  const report = {
    status: 'failed',
    fixture: input.fixture,
    synthetic: true,
    steps: [],
    model_request_attempts: 0,
    blocked_requests: 0,
    page_errors: 0,
  }
  let browser
  let context
  let page
  let watchdog
  let currentStep = 'launch_browser'
  async function step(name, operation) {
    currentStep = name
    await writeFile(
      join(output, 'progress.json'),
      JSON.stringify({ step: name }),
    )
    const started = performance.now()
    const result = { name, status: 'failed' }
    report.steps.push(result)
    try {
      const value = await operation()
      result.status = 'passed'
      return value
    } finally {
      result.elapsed_ms = Math.round((performance.now() - started) * 100) / 100
    }
  }
  try {
    browser = await chromium.launch({
      headless: true,
      ...(channel ? { channel } : {}),
    })
    context = await browser.newContext({
      viewport: { width: 390, height: 844 },
    })
    // Close pending UI/network work before the parent process's hard timeout.
    watchdog = setTimeout(() => {
      void context.close().catch(() => {})
    }, 180_000)
    await context.route('**/*', async (route) => {
      try {
        const request = route.request()
        boundary.admit(
          request.url(),
          request.method(),
          request.headers(),
          request.postData() ? request.postDataJSON() : null,
        )
        await route.continue()
      } catch {
        report.blocked_requests++
        await route.abort('blockedbyclient')
      }
    })
    page = await context.newPage()
    page.setDefaultTimeout(20_000)
    page.on('pageerror', () => report.page_errors++)
    async function connect() {
      await page.getByText('Backend connection', { exact: true }).click()
      await page
        .getByText('Protected server (optional)', { exact: true })
        .click()
      await page.getByLabel('Server access token').fill(input.token)
      await page.getByRole('button', { name: 'Connect', exact: true }).click()
      await expect(page.getByText('Ready', { exact: true })).toBeVisible()
    }
    async function response(path, action, status = 200) {
      const pending = page.waitForResponse(
        (reply) =>
          reply.url() === origin + path && reply.request().method() === 'POST',
        { timeout: 80_000 },
      )
      await action()
      const reply = await pending
      assert.equal(reply.status(), status)
      return reply.json()
    }
    await step('cache_app_and_connect', async () => {
      await page.goto(origin)
      await page.waitForFunction(() =>
        Boolean(navigator.serviceWorker.controller),
      )
      await connect()
    })
    await step('generate_and_save_mission', async () => {
      await page.getByLabel('What are the conditions?').selectOption('daylight')
      await page
        .getByLabel('What draws your attention?')
        .selectOption('textures')
      const create = page.getByRole('button', {
        name: /Create my small outing/,
      })
      await expect(create).toBeDisabled()
      await page
        .getByRole('checkbox', { name: /these selections go to hosted Qwen/ })
        .check()
      report.mission = await response(
        '/api/missions',
        () => create.click(),
        201,
      )
      await expect(
        page.getByRole('heading', {
          name: report.mission.mission.title,
          exact: true,
        }),
      ).toBeVisible()
      await expect(
        page.getByText('Saved on this device · ready to reopen offline'),
      ).toBeVisible()
      await page.screenshot({
        path: join(output, '01-mission.png'),
        fullPage: true,
      })
    })
    await step('offline_reload_and_save_fictional_observation', async () => {
      await page.getByRole('button', { name: /I’m heading out/ }).click()
      await context.setOffline(true)
      await page.reload()
      await expect(
        page.getByRole('heading', {
          name: report.mission.mission.title,
          exact: true,
        }),
      ).toBeVisible()
      await expect(
        page.getByRole('button', { name: /Create my small outing/ }),
      ).toBeDisabled()
      assert.equal(boundary.modelAttempts, 1)
      await page.getByRole('button', { name: /I’m heading out/ }).click()
      await page
        .getByRole('button', { name: 'I’m back — record an observation' })
        .click()
      await page
        .getByLabel('How did the mission fit?')
        .selectOption('too_difficult')
      await page.getByLabel('What did you notice?').fill(input.observation)
      await page
        .getByRole('button', { name: 'Save observation on this device' })
        .click()
      await expect(
        page.getByText(
          'Observation saved on this device. Not uploaded, and not sent to AI.',
        ),
      ).toBeVisible()
      await page.reload()
      await expect(
        page.getByText(input.observation, { exact: true }),
      ).toBeVisible()
      assert.equal(boundary.uploads, 0)
      await page
        .locator('section.journal')
        .screenshot({ path: join(output, '02-offline-note.png') })
    })
    await step('explicit_sync_and_exact_cloud_readback', async () => {
      await context.setOffline(false)
      await connect()
      await page.getByRole('button', { name: 'Check Atlas status' }).click()
      await expect(
        page.getByText(
          'Atlas sync configured; this status does not prove a database connection.',
        ),
      ).toBeVisible()
      const sync = page.getByRole('button', { name: 'Sync pending changes' })
      await expect(sync).toBeDisabled()
      await page.getByRole('checkbox', { name: /For this sync/ }).check()
      await response('/api/journal/entries', () => sync.click())
      await expect(
        page.getByText(
          '1 journal change confirmed by Atlas. No AI request was made.',
        ),
      ).toBeVisible()
      const pending = page.waitForResponse(origin + '/api/journal/entries')
      await page.getByRole('button', { name: 'Load cloud journal' }).click()
      const reply = await pending
      assert.equal(reply.status(), 200)
      const cloud = await reply.json()
      assert.equal(cloud.owner_id, input.owner)
      assert.equal(cloud.next_after, null)
      assert.deepEqual(
        cloud.entries.map((row) => row.entry),
        [boundary.entry],
      )
      assert.equal(boundary.entry.mission.id, report.mission.id)
      assert.deepEqual(boundary.entry.mission.mission, report.mission.mission)
      assert.deepEqual(
        boundary.entry.mission.generation,
        report.mission.generation,
      )
    })
    await step('review_selected_note_and_request_followup', async () => {
      await page
        .getByRole('button', { name: 'Check follow-up availability' })
        .click()
      await expect(
        page.getByText(
          'Model and journal settings are enabled. This check does not verify the selected Atlas records.',
        ),
      ).toBeVisible()
      await page
        .getByLabel('Observation to reflect on')
        .selectOption(boundary.entry.id)
      await expect(page.getByLabel('Selected data for review')).toContainText(
        input.observation,
      )
      const reflect = page.getByRole('button', {
        name: 'Reflect and suggest a mission',
      })
      await expect(reflect).toBeDisabled()
      await page
        .getByRole('checkbox', {
          name: /I approve sending this selected history/,
        })
        .check()
      report.followup = await response('/api/followups', () => reflect.click())
      assert.deepEqual(report.followup.source_ids, [boundary.entry.id])
      await expect(
        page.getByText('MODEL-GENERATED REFLECTION', { exact: true }),
      ).toBeVisible()
      await page
        .locator('.followup-suggestion')
        .screenshot({ path: join(output, '03-followup.png') })
      await page.getByRole('button', { name: 'Use this next mission' }).click()
      await expect(
        page.getByText('Next mission saved on this device.'),
      ).toBeVisible()
      await expect(
        page.getByRole('heading', {
          name: report.followup.mission.mission.title,
          exact: true,
        }),
      ).toBeVisible()
    })
    await step('explicit_cloud_deletion', async () => {
      await page.getByRole('button', { name: 'Remove observation' }).click()
      await page.getByRole('button', { name: 'Confirm removal' }).click()
      await expect(page.getByText(/Cloud deletion pending/)).toBeVisible()
      await page.getByRole('checkbox', { name: /For this sync/ }).check()
      await page.getByRole('button', { name: 'Sync pending changes' }).click()
      await expect(
        page.getByText(
          '1 journal change confirmed by Atlas. No AI request was made.',
        ),
      ).toBeVisible()
      assert.equal(boundary.deletes, 1)
    })
    await step(
      'saved_followup_reopens_offline_without_another_request',
      async () => {
        await context.setOffline(true)
        await page.reload()
        await expect(
          page.getByRole('heading', {
            name: report.followup.mission.mission.title,
            exact: true,
          }),
        ).toBeVisible()
        await expect(
          page.getByText(input.observation, { exact: true }),
        ).toHaveCount(0)
        assert.equal(boundary.modelAttempts, 2)
        assert.equal(report.blocked_requests, 0)
        assert.equal(report.page_errors, 0)
        const urls = await page.evaluate(async () => {
          const result = []
          for (const name of await caches.keys())
            for (const request of await (await caches.open(name)).keys())
              result.push(request.url)
          return result
        })
        assert.equal(
          urls.some(
            (url) => url.includes('/api/') || url.includes(input.token),
          ),
          false,
        )
      },
    )
    report.status = 'passed'
  } catch {
    report.failed_step = currentStep
    if (page) {
      await page
        .screenshot({ path: join(output, 'failed-step.png'), fullPage: true })
        .catch(() => {})
      report.cache_diagnostic = await page
        .evaluate(async () => ({
          secure_context: window.isSecureContext,
          has_controller: Boolean(navigator.serviceWorker?.controller),
          worker_states: (
            (await navigator.serviceWorker?.getRegistrations()) ?? []
          ).map((registration) => ({
            active: registration.active?.state ?? null,
            installing: registration.installing?.state ?? null,
            waiting: registration.waiting?.state ?? null,
          })),
        }))
        .catch(() => null)
    }
  } finally {
    clearTimeout(watchdog)
    await context?.close()
    await browser?.close()
    report.model_request_attempts = boundary.modelAttempts
    await writeFile(
      join(output, 'browser.json'),
      JSON.stringify(report, null, 2) + '\n',
      { flag: 'wx' },
    )
  }
  process.exitCode = report.status === 'passed' ? 0 : 1
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  main().catch(() => {
    process.exitCode = 1
  })
}

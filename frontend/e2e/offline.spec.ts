import { expect, test, type BrowserContext } from '@playwright/test'
import { mission, status } from '../src/test/fixtures'
import { journalStatus, owner } from '../src/journal/test-fixtures'

const fixture = {
  ...mission,
  mission: { ...mission.mission, title: 'E2E fixture — not model output' },
}
const token = 'fictional-browser-test-token-only'

async function fixtureApi(
  context: BrowserContext,
  enabled = true,
  protectedAccess = false,
) {
  const requests: string[] = []
  await context.route('**/api/**', async (route) => {
    const request = route.request()
    requests.push(request.url())
    expect(request.headers().authorization).toBe(
      protectedAccess ? `Bearer ${token}` : undefined,
    )
    if (request.url().endsWith('/api/model/status')) {
      await route.fulfill({
        json: {
          ...status,
          enabled,
          disabled_reason: enabled ? null : 'hosted_requests_disabled',
        },
      })
    } else if (request.url().endsWith('/api/missions')) {
      expect(request.method()).toBe('POST')
      expect(request.postDataJSON()).toEqual({
        minutes: 15,
        setting: 'courtyard',
        conditions: 'evening',
        focus: 'general',
      })
      await route.fulfill({ status: 201, json: fixture })
    } else throw new Error('unexpected_private_request')
  })
  return requests
}

test('production app reopens a saved fixture offline without credentials or another model call', async ({
  page,
  context,
}) => {
  const requests = await fixtureApi(context, true, true)
  page.on('console', (message) => {
    if (message.type() === 'error')
      console.error('Browser test:', message.text())
  })
  page.on('requestfailed', (request) =>
    console.error(
      'Browser test request failed:',
      request.url(),
      request.failure()?.errorText,
    ),
  )
  await page.goto('/')
  await expect(
    page.getByText(
      'Offline app shell cached. Save a mission before disconnecting.',
    ),
  ).toBeVisible()
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller))
  expect(requests).toHaveLength(0)
  await expect(page.getByText('An app update is ready.')).toHaveCount(0)
  await page.getByText('Backend connection', { exact: true }).click()
  await page.getByText('Protected server (optional)', { exact: true }).click()
  await page.getByLabel('Server access token').fill(token)
  await page.getByRole('button', { name: 'Connect', exact: true }).click()
  await expect(page.getByText('Ready', { exact: true })).toBeVisible()
  await page
    .getByRole('checkbox', { name: /these selections go to hosted Qwen/ })
    .check()
  await page.getByRole('button', { name: /Create my small outing/ }).click()
  await expect(
    page.getByRole('heading', { name: fixture.mission.title }),
  ).toBeVisible()
  await expect(
    page.getByText('Saved on this device · ready to reopen offline'),
  ).toBeVisible()
  expect(requests).toHaveLength(2)
  await page.getByRole('button', { name: /I’m heading out/ }).click()
  await expect(
    page.getByText(/does not mark this mission complete/),
  ).toBeVisible()
  await context.setOffline(true)
  await expect(page.getByText('Device offline')).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('heading', { name: fixture.mission.title }),
  ).toBeVisible()
  await expect(
    page.getByText('Saved on this device · ready to reopen offline'),
  ).toBeVisible()
  await page.getByText('Backend connection', { exact: true }).click()
  await expect(page.getByLabel('Server access token')).toHaveValue('')
  await expect(
    page.getByRole('button', { name: /Create my small outing/ }),
  ).toBeDisabled()
  expect(requests).toHaveLength(2)
  expect(
    await page.evaluate(() => ({
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ local: 0, session: 0 })
  const cacheURLs = await page.evaluate(async () => {
    const urls: string[] = []
    for (const name of await caches.keys()) {
      for (const request of await (await caches.open(name)).keys())
        urls.push(request.url)
    }
    return urls
  })
  expect(
    cacheURLs.some((url) => url.includes('/api/') || url.includes(token)),
  ).toBe(false)
  expect(cacheURLs.some((url) => url.endsWith('/index.html'))).toBe(true)
  await page.getByText('Backend connection', { exact: true }).click()
  const card = await page
    .getByRole('heading', { name: fixture.mission.title })
    .boundingBox()
  const builder = await page
    .getByRole('heading', { name: 'Make room for a small lap.' })
    .boundingBox()
  expect(card!.y).toBeLessThan(builder!.y)
  await page.getByRole('button', { name: /I’m heading out/ }).click()
  await page.screenshot({
    path: 'test-results/offline-phone-width.png',
    fullPage: true,
  })
})

test('mobile and desktop preparation fit without horizontal overflow', async ({
  page,
}) => {
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Your outing starts here.' }),
  ).toBeVisible()
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
    await expect(
      page.getByRole('button', { name: /Create my small outing/ }),
    ).toBeDisabled()
  }
  await page.screenshot({
    path: 'test-results/desktop-preparation.png',
    fullPage: true,
  })
})

test('a disabled hosted provider never permits mission generation', async ({
  page,
  context,
}) => {
  const requests = await fixtureApi(context, false)
  await page.goto('/')
  await page.getByText('Backend connection', { exact: true }).click()
  await page
    .getByRole('button', { name: 'Connect to local backend', exact: true })
    .click()
  await expect(page.getByText('Connected · generation off')).toBeVisible()
  await page
    .getByRole('checkbox', { name: /these selections go to hosted Qwen/ })
    .check()
  await expect(
    page.getByRole('button', { name: /Create my small outing/ }),
  ).toBeDisabled()
  expect(requests).toHaveLength(1)
})

test('offline observations survive reload and explicit sync safely replays a lost reply', async ({
  page,
  context,
}) => {
  const modelRequests = await fixtureApi(context)
  const cloud = new Map<string, Record<string, unknown>>()
  let uploads = 0
  await context.route('**/api/journal/**', async (route) => {
    const request = route.request()
    expect(request.headers().authorization).toBeUndefined()
    if (request.url().endsWith('/status')) {
      await route.fulfill({ json: journalStatus })
    } else if (request.method() === 'POST') {
      const body = request.postDataJSON()
      expect(body.owner_id).toBe(owner)
      expect(body.entry.observation).toBe(
        'Browser-test observation — fictional, not an outdoor result.',
      )
      ++uploads
      cloud.set(body.entry.id, body.entry)
      if (uploads === 1) await route.abort('failed')
      else
        await route.fulfill({
          json: { owner_id: owner, id: body.entry.id, status: 'stored' },
        })
    } else if (request.method() === 'DELETE') {
      const id = request.url().split('/').at(-1)!
      expect(request.headers()['x-onelap-journal-owner']).toBe(owner)
      expect(request.postData()).toBeNull()
      cloud.set(id, { deleted: true })
      await route.fulfill({ json: { owner_id: owner, id, status: 'deleted' } })
    } else throw new Error('unexpected_test_journal_read')
  })
  await page.goto('/')
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller))
  await page.getByText('Backend connection', { exact: true }).click()
  await page
    .getByRole('button', { name: 'Connect to local backend', exact: true })
    .click()
  await expect(page.getByText('Ready', { exact: true })).toBeVisible()
  await page
    .getByRole('checkbox', { name: /these selections go to hosted Qwen/ })
    .check()
  await page.getByRole('button', { name: /Create my small outing/ }).click()
  await expect(
    page.getByText('Saved on this device · ready to reopen offline'),
  ).toBeVisible()
  await page.getByRole('button', { name: /I’m heading out/ }).click()
  await context.setOffline(true)
  await page
    .getByRole('button', { name: 'I’m back — record an observation' })
    .click()
  const observation =
    'Browser-test observation — fictional, not an outdoor result.'
  await page.getByLabel('What did you notice?').fill(observation)
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
  expect(uploads).toBe(0)
  await page
    .locator('section.journal')
    .screenshot({ path: 'test-results/offline-journal-fixture.png' })
  await context.setOffline(false)
  await page.getByText('Backend connection', { exact: true }).click()
  await page
    .getByRole('button', { name: 'Connect to local backend', exact: true })
    .click()
  await expect(page.getByText('Ready', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Check Atlas status' }).click()
  await expect(
    page.getByText(
      'Atlas sync configured; this status does not prove a database connection.',
    ),
  ).toBeVisible()
  await page.getByRole('checkbox', { name: /For this sync/ }).check()
  await page.getByRole('button', { name: 'Sync pending changes' }).click()
  await expect(page.getByRole('alert')).toContainText('could not be confirmed')
  expect(uploads).toBe(1)
  expect(cloud.size).toBe(1)
  await page.getByRole('checkbox', { name: /For this sync/ }).check()
  await page.getByRole('button', { name: 'Sync pending changes' }).click()
  await expect(
    page.getByText(
      '1 journal change confirmed by Atlas. No AI request was made.',
    ),
  ).toBeVisible()
  expect(uploads).toBe(2)
  expect(cloud.size).toBe(1)
  await page.getByRole('button', { name: 'Remove observation' }).click()
  await page.getByRole('button', { name: 'Confirm removal' }).click()
  await expect(page.getByText(/Cloud deletion pending/)).toBeVisible()
  await expect(page.getByText(observation, { exact: true })).toHaveCount(0)
  await page.getByRole('checkbox', { name: /For this sync/ }).check()
  await page.getByRole('button', { name: 'Sync pending changes' }).click()
  await expect(
    page.getByText(
      '1 journal change confirmed by Atlas. No AI request was made.',
    ),
  ).toBeVisible()
  expect([...cloud.values()]).toEqual([{ deleted: true }])
  expect(
    modelRequests.filter((url) => url.endsWith('/api/missions')),
  ).toHaveLength(1)
})

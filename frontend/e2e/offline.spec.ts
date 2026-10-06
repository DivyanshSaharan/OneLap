import { expect, test, type BrowserContext } from '@playwright/test'
import { mission, status } from '../src/test/fixtures'

const fixture = {
  ...mission,
  mission: { ...mission.mission, title: 'E2E fixture — not model output' },
}
const token = 'fictional-browser-test-token-only'

async function fixtureApi(context: BrowserContext, enabled = true) {
  const requests: string[] = []
  await context.route('**/api/**', async (route) => {
    const request = route.request()
    requests.push(request.url())
    expect(request.headers().authorization).toBe(`Bearer ${token}`)
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
  const requests = await fixtureApi(context)
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
  await page.getByText('Private access', { exact: true }).click()
  await page.getByLabel('Server access token').fill(token)
  await page.getByRole('button', { name: 'Connect', exact: true }).click()
  await expect(page.getByText('Ready', { exact: true })).toBeVisible()
  await page.getByRole('checkbox').check()
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
  await page.getByText('Private access', { exact: true }).click()
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
  await page.getByText('Private access', { exact: true }).click()
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
  await page.getByText('Private access', { exact: true }).click()
  await page.getByLabel('Server access token').fill(token)
  await page.getByRole('button', { name: 'Connect', exact: true }).click()
  await expect(page.getByText('Connected · generation off')).toBeVisible()
  await page.getByRole('checkbox').check()
  await expect(
    page.getByRole('button', { name: /Create my small outing/ }),
  ).toBeDisabled()
  expect(requests).toHaveLength(1)
})

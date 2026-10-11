import { expect, test } from '@playwright/test'
import { mission, status } from '../src/test/fixtures'
import {
  journalStatus,
  outing,
  owner,
  otherOwner,
} from '../src/journal/test-fixtures'

test('Google fixture login restores on reload, isolates local accounts and never syncs without approval', async ({
  page,
  context,
}) => {
  const csrf = 'a'.repeat(43)
  let signedIn: string | null = null
  let missions = 0
  let journalWrites = 0
  let logins = 0
  await context.addInitScript(() => {
    let callback: (value: { credential: string }) => void
    Object.assign(window, {
      google: {
        accounts: {
          id: {
            initialize: (options: {
              nonce: string
              callback: typeof callback
            }) => {
              callback = options.callback
            },
            renderButton: (container: HTMLElement) => {
              const button = document.createElement('button')
              button.textContent = 'Continue with Google — offline fixture'
              button.onclick = () =>
                callback({ credential: 'fictional-id-token' })
              container.append(button)
            },
            disableAutoSelect: () => {},
          },
        },
      },
    })
  })
  await context.route('**/api/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const identity = {
      enabled: true,
      client_id: 'fictional.apps.googleusercontent.com',
      owner_id: signedIn,
      csrf: signedIn ? csrf : null,
    }
    expect(request.headers().authorization).toBeUndefined()
    if (path === '/api/auth/session') return route.fulfill({ json: identity })
    if (path === '/api/auth/challenge')
      return route.fulfill({ json: { nonce: 'n'.repeat(43), csrf } })
    if (path === '/api/auth/google') {
      expect(request.postDataJSON()).toEqual({
        credential: 'fictional-id-token',
        csrf,
      })
      signedIn = ++logins === 2 ? otherOwner : owner
      return route.fulfill({
        json: { ...identity, owner_id: signedIn, csrf },
        headers: {
          'set-cookie':
            'onelap_session=fictional-browser-session; Path=/; HttpOnly; SameSite=Strict',
        },
      })
    }
    if (path === '/api/auth/logout') {
      expect(request.headers()['x-onelap-csrf']).toBe(csrf)
      signedIn = null
      return route.fulfill({
        json: { status: 'signed_out' },
        headers: {
          'set-cookie':
            'onelap_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0',
        },
      })
    }
    expect(signedIn).not.toBeNull()
    expect(request.headers().cookie).toContain('onelap_session=')
    if (path === '/api/model/status') return route.fulfill({ json: status })
    if (path === '/api/journal/status')
      return route.fulfill({ json: { ...journalStatus, owner_id: signedIn } })
    if (path === '/api/missions') {
      ++missions
      expect(request.headers()['x-onelap-csrf']).toBe(csrf)
      return route.fulfill({ status: 201, json: mission })
    }
    ++journalWrites
    throw new Error(
      'Unexpected cloud journal request in consent-free auth fixture',
    )
  })
  await page.goto('/')
  async function expectLocked() {
    await expect(
      page.getByRole('button', { name: /Create my small outing/ }),
    ).toHaveCount(0)
    await expect(
      page.getByRole('heading', { name: mission.mission.title }),
    ).toHaveCount(0)
    await expect(page.getByLabel('What did you notice?')).toHaveCount(0)
    await expect(page.getByText('Backend connection')).toHaveCount(0)
  }
  await expect(
    page.getByRole('button', { name: 'Sign in with Google', exact: true }),
  ).toBeEnabled()
  await expectLocked()
  await expect(
    page
      .locator('header')
      .getByRole('button', { name: 'Sign in with Google', exact: true }),
  ).toBeVisible()
  await expect(page.getByText(/minimal session in Atlas/)).toHaveCount(0)
  await expect(
    page.getByText(/Saved notes remain on this device after sign-out/),
  ).toHaveCount(0)
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 844 })
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
  }
  await page.screenshot({
    path: '.data/auth-signin-desktop.png',
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: '.data/auth-signin-390.png', fullPage: true })

  async function login() {
    await page
      .getByRole('button', { name: 'Sign in with Google', exact: true })
      .click()
    await page
      .getByRole('button', { name: 'Continue with Google — offline fixture' })
      .click()
    await expect(
      page.getByRole('button', { name: 'Sign out', exact: true }),
    ).toBeEnabled()
    await expect(
      page.getByRole('button', { name: 'Reconnect my journal' }),
    ).toHaveCount(0)
  }
  await login()
  await page
    .getByRole('checkbox', { name: /these selections go to hosted Qwen/ })
    .check()
  await page.getByRole('button', { name: /Create my small outing/ }).click()
  await page.getByText('Record an observation', { exact: true }).click()
  await page
    .getByLabel('What did you notice?')
    .fill('Account A fictional local observation.')
  await page
    .getByRole('button', { name: 'Save observation on this device' })
    .click()
  await expect(
    page.getByText('Account A fictional local observation.', { exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('heading', { name: mission.mission.title, level: 2 }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Sign out', exact: true }),
  ).toBeEnabled()
  await expect(
    page.getByText('Account A fictional local observation.', { exact: true }),
  ).toBeVisible()
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    'onelap_session',
  )
  await page.screenshot({ path: '.data/auth-account-390.png', fullPage: true })
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Sign in with Google', exact: true }),
  ).toBeEnabled()
  await expectLocked()
  await expect(
    page.getByText('Account A fictional local observation.', { exact: true }),
  ).toHaveCount(0)
  await context.setOffline(true)
  await page.reload()
  await expect(page.getByText(/Connect to verify your sign-in/)).toBeVisible()
  await expectLocked()
  await context.setOffline(false)
  await expect(
    page.getByRole('button', { name: 'Sign in with Google', exact: true }),
  ).toBeEnabled()
  await login()
  await expect(
    page.getByText('Account A fictional local observation.', { exact: true }),
  ).toHaveCount(0)
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await login()
  await expect(
    page.getByText('Account A fictional local observation.', { exact: true }),
  ).toBeVisible()
  expect(missions).toBe(1)
  expect(journalWrites).toBe(0)
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  )
  expect(overflow).toBe(false)
})

test('a fresh signed-in device can explicitly load cloud history without creating a mission', async ({
  page,
  context,
}) => {
  const csrf = 'a'.repeat(43)
  let signedIn = true
  let journalReads = 0
  let journalWrites = 0
  let modelRequests = 0
  await context.route('**/api/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/auth/session')
      return route.fulfill({
        json: {
          enabled: true,
          client_id: 'fictional.apps.googleusercontent.com',
          owner_id: signedIn ? owner : null,
          csrf: signedIn ? csrf : null,
        },
      })
    expect(signedIn).toBe(true)
    if (path === '/api/model/status') return route.fulfill({ json: status })
    if (path === '/api/journal/status')
      return route.fulfill({ json: journalStatus })
    if (path === '/api/journal/entries') {
      if (request.method() !== 'GET') {
        ++journalWrites
        throw new Error('Unexpected journal upload in explicit-load fixture')
      }
      ++journalReads
      expect(request.headers()['x-onelap-journal-owner']).toBe(owner)
      return route.fulfill({
        json: {
          owner_id: owner,
          entries: [
            {
              entry: outing,
              received_at: '2026-10-06T14:01:00.000Z',
              mission_source: 'client_submitted',
            },
          ],
          next_after: null,
        },
      })
    }
    if (path === '/api/auth/logout') {
      expect(request.headers()['x-onelap-csrf']).toBe(csrf)
      signedIn = false
      return route.fulfill({ json: { status: 'signed_out' } })
    }
    if (path === '/api/missions' || path === '/api/followups') ++modelRequests
    throw new Error('Unexpected API request in fresh-device cloud fixture')
  })
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Your journal.' }),
  ).toBeVisible()
  await expect(
    page.getByText('Record an observation', { exact: true }),
  ).toHaveCount(0)
  await expect(page.getByLabel('What did you notice?')).toHaveCount(0)
  await expect(
    page.getByRole('heading', { name: mission.mission.title, level: 2 }),
  ).toHaveCount(0)
  expect(journalReads).toBe(0)
  expect(journalWrites).toBe(0)
  expect(modelRequests).toBe(0)

  await page.getByText('Cloud sync & privacy', { exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Load cloud journal' }),
  ).toBeDisabled()
  await page.getByRole('button', { name: 'Check Atlas status' }).click()
  await expect(
    page.getByRole('button', { name: 'Load cloud journal' }),
  ).toBeEnabled()
  expect(journalReads).toBe(0)
  await page.getByRole('button', { name: 'Load cloud journal' }).click()
  await expect(
    page.getByText(outing.observation, { exact: true }),
  ).toBeVisible()
  expect(journalReads).toBe(1)
  expect(journalWrites).toBe(0)
  expect(modelRequests).toBe(0)
  await expect(
    page.getByRole('button', { name: 'Sync pending changes' }),
  ).toBeDisabled()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(
    page.getByText('Cloud sync & privacy', { exact: true }),
  ).toHaveCount(0)
  await expect(page.getByText(outing.observation, { exact: true })).toHaveCount(
    0,
  )
  await expect(
    page.getByRole('heading', { name: 'Your journal.' }),
  ).toHaveCount(0)
  expect(journalReads).toBe(1)
  expect(journalWrites).toBe(0)
  expect(modelRequests).toBe(0)
})

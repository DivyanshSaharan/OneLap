import { afterEach, expect, it, vi } from 'vitest'
import { ApiError, privateRequest, setSessionTransport } from '../api'
import { getChallenge, getSession, login, logout, parseSession } from './api'

const owner = '11111111-1111-4111-8111-111111111111'
const other = '22222222-2222-4222-8222-222222222222'
const csrf = 'a'.repeat(43)
const session = {
  enabled: true,
  client_id: 'fictional.apps.googleusercontent.com',
  owner_id: owner,
  csrf,
}
const reply = (value: unknown, ok = true) =>
  ({ ok, json: async () => value }) as Response

afterEach(() => {
  setSessionTransport(false, null, null)
  vi.restoreAllMocks()
})

it('accepts disabled, logged-out and authenticated session shapes', () => {
  expect(parseSession(session)).toEqual(session)
  expect(
    parseSession({ ...session, owner_id: null, csrf: null }).owner_id,
  ).toBeNull()
  expect(
    parseSession({
      enabled: false,
      client_id: null,
      owner_id: null,
      csrf: null,
    }).enabled,
  ).toBe(false)
})

it.each([
  { ...session, owner_id: other, csrf: null },
  { ...session, owner_id: null },
  { ...session, csrf: 'short' },
  { ...session, owner_id: 'not-uuid' },
  { ...session, enabled: false },
  { ...session, client_id: 'wrong' },
  { ...session, access_token: 'must-not-exist' },
])('rejects malformed identity metadata %j', (value) => {
  expect(() => parseSession(value)).toThrow()
})

it('checks session with same-origin cookies, never Google credentials', async () => {
  const fetch = vi.fn().mockResolvedValue(reply(session))
  vi.stubGlobal('fetch', fetch)
  expect(await getSession()).toEqual(session)
  expect(fetch.mock.calls[0][1]).toMatchObject({
    credentials: 'same-origin',
    cache: 'no-store',
  })
  expect(fetch.mock.calls[0][1].headers).not.toHaveProperty('Authorization')
})

it('validates challenge shape and keeps credentials only in the login body', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(reply({ nonce: 'n'.repeat(43), csrf }))
    .mockResolvedValueOnce(reply(session))
  vi.stubGlobal('fetch', fetch)
  expect((await getChallenge()).csrf).toBe(csrf)
  expect(await login('fictional-id-token', csrf)).toEqual(session)
  expect(fetch.mock.calls[1][0]).toBe('/api/auth/google')
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    credential: 'fictional-id-token',
    csrf,
  })
})

it('sends CSRF and cookies for mutations but suppresses legacy bearer tokens', async () => {
  setSessionTransport(true, csrf, owner)
  const fetch = vi.fn().mockResolvedValue(reply({ status: 'signed_out' }))
  vi.stubGlobal('fetch', fetch)
  await logout()
  expect(fetch.mock.calls[0][1]).toMatchObject({
    credentials: 'same-origin',
    headers: { 'X-OneLap-CSRF': csrf },
  })
  await privateRequest(
    '/api/journal/entries',
    'old-legacy-token',
    undefined,
    'GET',
    owner,
  )
  expect(fetch.mock.calls[1][1].headers).not.toHaveProperty('Authorization')
})

it('blocks a different owner before fetch', async () => {
  setSessionTransport(true, csrf, owner)
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  await expect(
    privateRequest('/api/journal/entries', '', undefined, 'GET', other),
  ).rejects.toMatchObject({ code: 'session_changed' })
  expect(fetch).not.toHaveBeenCalled()
})

it('discards an in-flight reply after account switching', async () => {
  setSessionTransport(true, csrf, owner)
  let resolve!: (response: Response) => void
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(
      () =>
        new Promise<Response>((done) => {
          resolve = done
        }),
    ),
  )
  const pending = privateRequest(
    '/api/journal/entries',
    '',
    undefined,
    'GET',
    owner,
  )
  setSessionTransport(true, 'b'.repeat(43), other)
  resolve(reply({ owner_id: owner, entries: [] }))
  await expect(pending).rejects.toMatchObject({ code: 'session_changed' })
})

it('announces expired sessions without retrying or persisting secrets', async () => {
  setSessionTransport(true, csrf, owner)
  const expired = vi.fn()
  window.addEventListener('onelap:session-expired', expired)
  const fetch = vi
    .fn()
    .mockResolvedValue(reply({ error: 'sign_in_required' }, false))
  vi.stubGlobal('fetch', fetch)
  await expect(privateRequest('/api/model/status', '')).rejects.toBeInstanceOf(
    ApiError,
  )
  expect(expired).toHaveBeenCalledOnce()
  expect(fetch).toHaveBeenCalledOnce()
  expect(localStorage.length).toBe(0)
  window.removeEventListener('onelap:session-expired', expired)
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, explain, generateMission, getStatus } from './api'
import { input, mission, status } from './test/fixtures'

function reply(value: unknown, ok = true) {
  return { ok, status: ok ? 200 : 503, json: async () => value } as Response
}
afterEach(() => vi.restoreAllMocks())

describe('private requests', () => {
  it('omits authorization for token-free local access', async () => {
    const fetch = vi.fn().mockResolvedValue(reply(status))
    vi.stubGlobal('fetch', fetch)
    expect(await getStatus('')).toEqual(status)
    expect(fetch.mock.calls[0][1].headers).not.toHaveProperty('Authorization')
    expect(fetch.mock.calls[0][1].credentials).toBe('omit')
  })
  it('checks status without making a generation request', async () => {
    const fetch = vi.fn().mockResolvedValue(reply(status))
    vi.stubGlobal('fetch', fetch)
    expect(await getStatus('private-token')).toEqual(status)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch.mock.calls[0][0]).toBe('/api/model/status')
    expect(fetch.mock.calls[0][1]).toMatchObject({
      method: 'GET',
      cache: 'no-store',
      credentials: 'omit',
      headers: { Authorization: 'Bearer private-token' },
    })
  })
  it('sends only outing selections, never a key in the body or URL', async () => {
    const fetch = vi.fn().mockResolvedValue(reply(mission))
    vi.stubGlobal('fetch', fetch)
    expect(await generateMission('private-token', input)).toEqual(mission)
    expect(fetch.mock.calls[0][0]).toBe('/api/missions')
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(input)
    expect(fetch.mock.calls[0][1].body).not.toContain('private-token')
  })
  it('refuses offline calls before fetch', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await expect(generateMission('token', input)).rejects.toMatchObject({
      code: 'offline',
    })
    expect(fetch).not.toHaveBeenCalled()
  })
  it('does not automatically retry failures', async () => {
    const fetch = vi.fn().mockRejectedValue(new Error('PRIVATE_ERROR'))
    vi.stubGlobal('fetch', fetch)
    await expect(generateMission('token', input)).rejects.toMatchObject({
      code: 'network_unavailable',
    })
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(explain(new ApiError('network_unavailable'))).not.toContain(
      'PRIVATE_ERROR',
    )
  })
  it('passes stable backend codes without echoing arbitrary error details', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          reply(
            { error: 'hosted_requests_disabled', detail: 'PRIVATE' },
            false,
          ),
        ),
    )
    await expect(generateMission('token', input)).rejects.toMatchObject({
      code: 'hosted_requests_disabled',
    })
    expect(explain(new ApiError('hosted_requests_disabled'))).toContain(
      'switched off',
    )
  })
  it.each([
    [
      'atlas_budget_not_approved',
      'OneLap’s shared spending setup has not been approved yet. New missions are paused.',
    ],
    [
      'budget_import_required',
      'Earlier model spending needs to be added to OneLap’s records before new missions can be created.',
    ],
    [
      'budget_import_below_known_usage',
      'OneLap’s spending setup is missing some earlier usage. New missions are paused until it is corrected.',
    ],
    [
      'budget_import_below_local_ledger',
      'The spending setup is below this server’s recorded usage. New missions are paused until it is corrected.',
    ],
    [
      'budget_import_mismatch',
      'OneLap’s spending settings do not match its saved records. New missions are paused until they are corrected.',
    ],
    [
      'budget_ledger_scope_mismatch',
      'OneLap’s spending records belong to a different setup. New missions are paused until the server is checked.',
    ],
    [
      'budget_ledger_not_configured',
      'OneLap’s spending records are not connected yet. New missions are paused until the server setup is completed.',
    ],
    [
      'budget_reservation_conflict',
      'OneLap found conflicting spending records. New missions are paused until the server is checked.',
    ],
  ])(
    'explains spending setup error %s from a 503 status check without retrying',
    async (code, explanation) => {
      const fetch = vi
        .fn()
        .mockResolvedValue(
          reply({ error: code, detail: 'PRIVATE_SPENDING_DETAILS' }, false),
        )
      vi.stubGlobal('fetch', fetch)
      const error: unknown = await getStatus('private-token').catch(
        (failure: unknown) => failure,
      )
      expect(error).toBeInstanceOf(ApiError)
      expect(error).toMatchObject({ code })
      expect(explain(error)).toBe(explanation)
      expect(explain(error)).not.toContain('PRIVATE_SPENDING_DETAILS')
      expect(explain(error)).not.toContain(code)
      expect(fetch).toHaveBeenCalledExactlyOnceWith(
        '/api/model/status',
        expect.objectContaining({ method: 'GET' }),
      )
    },
  )
  it.each(['PRIVATE_ERROR_DETAILS', 'constructor', '__proto__', 'toString'])(
    'does not echo an unknown status error %s or its private details',
    async (code) => {
      const fetch = vi
        .fn()
        .mockResolvedValue(
          reply({ error: code, detail: 'PRIVATE_SPENDING_DETAILS' }, false),
        )
      vi.stubGlobal('fetch', fetch)
      const error: unknown = await getStatus('private-token').catch(
        (failure: unknown) => failure,
      )
      expect(explain(error)).toBe(
        'The API could not complete this action. No substitute mission was created.',
      )
      expect(explain(error)).not.toContain(code)
      expect(explain(error)).not.toContain('PRIVATE_SPENDING_DETAILS')
      expect(fetch).toHaveBeenCalledExactlyOnceWith(
        '/api/model/status',
        expect.objectContaining({ method: 'GET' }),
      )
    },
  )
  it('rejects a model response that changed preferences', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          reply({ ...mission, mission: { ...mission.mission, minutes: 20 } }),
        ),
    )
    await expect(generateMission('token', input)).rejects.toMatchObject({
      code: 'mission_constraint_mismatch',
    })
  })
  it('does not treat arbitrary HTML as a mission', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => {
          throw new Error('html')
        },
      }),
    )
    await expect(generateMission('token', input)).rejects.toBeInstanceOf(
      ApiError,
    )
  })
  it('bounds a stalled request and retains the no-retry warning', async () => {
    vi.useFakeTimers()
    const fetch = vi.fn(
      (_path, options) =>
        new Promise((_resolve, reject) => {
          options.signal.addEventListener('abort', () =>
            reject(new Error('aborted')),
          )
        }),
    )
    vi.stubGlobal('fetch', fetch)
    const pending = generateMission('token', input)
    const assertion = expect(pending).rejects.toMatchObject({
      code: 'request_timeout',
    })
    await vi.advanceTimersByTimeAsync(75_000)
    await assertion
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, explain, generateMission, getStatus } from './api'
import { input, mission, status } from './test/fixtures'

function reply(value: unknown, ok = true) {
  return { ok, json: async () => value } as Response
}
afterEach(() => vi.restoreAllMocks())

describe('private requests', () => {
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

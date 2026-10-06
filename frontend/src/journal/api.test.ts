import { expect, it, vi } from 'vitest'
import { ApiError } from '../api'
import { getJournalPage, getJournalStatus, sendRecord } from './api'
import { journalStatus, outing, owner } from './test-fixtures'

it('checks status without transmitting a journal entry', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify(journalStatus)))
  vi.stubGlobal('fetch', fetch)
  expect(await getJournalStatus('memory-only-token')).toEqual(journalStatus)
  expect(fetch.mock.calls[0][1].body).toBeUndefined()
})
it('uploads only an owner-bound entry and validates its acknowledgment', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(
        JSON.stringify({ owner_id: owner, id: outing.id, status: 'stored' }),
      ),
    )
  vi.stubGlobal('fetch', fetch)
  await sendRecord('token', owner, {
    version: 1,
    kind: 'entry',
    id: outing.id,
    owner_id: owner,
    stage: 'pending',
    entry: outing,
  })
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    owner_id: owner,
    entry: outing,
  })
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer token')
  expect(fetch).toHaveBeenCalledTimes(1)
})
it('sends deletion without a journal body and with the expected owner header', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(
        JSON.stringify({ owner_id: owner, id: outing.id, status: 'deleted' }),
      ),
    )
  vi.stubGlobal('fetch', fetch)
  await sendRecord('token', owner, {
    version: 1,
    kind: 'delete',
    id: outing.id,
    owner_id: owner,
  })
  expect(fetch.mock.calls[0][1]).toMatchObject({
    method: 'DELETE',
    headers: { 'X-OneLap-Journal-Owner': owner },
  })
  expect(fetch.mock.calls[0][1].body).toBeUndefined()
})
it('does not accept a spoofed owner or ID acknowledgment', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ owner_id: owner, id: owner, status: 'stored' }),
        ),
      ),
  )
  await expect(
    sendRecord('token', owner, {
      version: 1,
      kind: 'entry',
      id: outing.id,
      owner_id: owner,
      stage: 'pending',
      entry: outing,
    }),
  ).rejects.toThrow(ApiError)
})
it('offline cloud reads fail before fetch', async () => {
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
  await expect(getJournalPage('token', owner, null)).rejects.toThrow('offline')
  expect(fetch).not.toHaveBeenCalled()
})

import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { IDBFactory } from 'fake-indexeddb'
import { ApiError } from '../api'
import { mission } from '../test/fixtures'
import { loadOutbox, queueOuting } from './outbox'
import { journalStatus, otherOwner, outing, owner } from './test-fixtures'
import { useJournal } from './useJournal'

const mocks = vi.hoisted(() => ({
  status: vi.fn(),
  send: vi.fn(),
  page: vi.fn(),
}))
vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  getJournalStatus: mocks.status,
  sendRecord: mocks.send,
  getJournalPage: mocks.page,
}))
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('indexedDB', new IDBFactory())
  mocks.status.mockResolvedValue(journalStatus)
  mocks.send.mockResolvedValue(undefined)
  mocks.page.mockResolvedValue({
    owner_id: owner,
    entries: [],
    next_after: null,
  })
})

async function ready(token = 'private-memory-token', online = true) {
  const hook = renderHook(() => useJournal(token, online))
  await waitFor(() => expect(hook.result.current.restoring).toBe(false))
  return hook
}
it('does not contact Atlas or AI on startup, including with private access', async () => {
  await ready()
  expect(mocks.status).not.toHaveBeenCalled()
  expect(mocks.send).not.toHaveBeenCalled()
  expect(mocks.page).not.toHaveBeenCalled()
})
it('supports explicitly connected local access without a token', async () => {
  await queueOuting(outing)
  const hook = renderHook(() => useJournal('', true, true))
  await waitFor(() => expect(hook.result.current.restoring).toBe(false))
  await act(async () => {
    await hook.result.current.check()
  })
  await act(async () => {
    await hook.result.current.sync([outing.id])
  })
  expect(mocks.status).toHaveBeenCalledWith('')
  expect(mocks.send).toHaveBeenCalledWith(
    '',
    owner,
    expect.objectContaining({ id: outing.id }),
  )
  expect(hook.result.current.records[0]).toMatchObject({ stage: 'synced' })
})
it('captures an observation offline, with no cloud or model requests', async () => {
  const { result } = await ready('', false)
  await act(async () => {
    await result.current.capture(mission, {
      outcome: 'completed',
      observation: 'A soft shadow.',
      feedback: null,
    })
  })
  expect(result.current.records).toHaveLength(1)
  expect(result.current.records[0]).toMatchObject({
    owner_id: null,
    stage: 'pending',
    entry: { observation: 'A soft shadow.' },
  })
  expect(mocks.send).not.toHaveBeenCalled()
  expect(mocks.status).not.toHaveBeenCalled()
})
it('refreshes the outbox on remount without automatically uploading', async () => {
  await queueOuting(outing)
  const first = await ready()
  first.unmount()
  const second = await ready()
  expect(second.result.current.records[0]).toMatchObject({ entry: outing })
  expect(mocks.send).not.toHaveBeenCalled()
})
it('requires a manually checked owner before any sync', async () => {
  await queueOuting(outing)
  const { result } = await ready()
  await act(async () => {
    await result.current.sync([outing.id])
  })
  expect(mocks.send).not.toHaveBeenCalled()
  await act(async () => {
    await result.current.check()
  })
  await act(async () => {
    await result.current.sync([outing.id])
  })
  expect(mocks.send).toHaveBeenCalledTimes(1)
  expect(result.current.records[0]).toMatchObject({
    owner_id: owner,
    stage: 'synced',
  })
})
it('retains the same owner, entry ID and content after a lost acknowledgment', async () => {
  await queueOuting(outing)
  const { result } = await ready()
  await act(async () => {
    await result.current.check()
  })
  mocks.send.mockRejectedValueOnce(new ApiError('network_unavailable'))
  await act(async () => {
    await result.current.sync([outing.id])
  })
  expect(result.current.records[0]).toMatchObject({
    owner_id: owner,
    stage: 'pending',
    entry: outing,
  })
  expect(mocks.send).toHaveBeenCalledTimes(1)
  await act(async () => {
    await result.current.sync([outing.id])
  })
  expect(mocks.send.mock.calls[0]).toEqual(mocks.send.mock.calls[1])
  expect(result.current.records[0]).toMatchObject({ stage: 'synced' })
})
it('never uploads another owners bound records', async () => {
  await queueOuting(outing)
  const { bindForSync } = await import('./outbox')
  await bindForSync(outing.id, otherOwner)
  const { result } = await ready()
  await act(async () => {
    await result.current.check()
  })
  await act(async () => {
    await result.current.sync([outing.id])
  })
  expect(mocks.send).not.toHaveBeenCalled()
  expect(result.current.records[0].owner_id).toBe(otherOwner)
})
it('does not upload a note added by another tab after consent was given', async () => {
  await queueOuting(outing)
  const { result } = await ready()
  await act(async () => {
    await result.current.check()
  })
  const extra = { ...outing, id: otherOwner }
  await queueOuting(extra)
  await act(async () => {
    await result.current.sync([outing.id])
  })
  expect(mocks.send).toHaveBeenCalledTimes(1)
  expect((await loadOutbox()).find((row) => row.id === extra.id)).toMatchObject(
    { owner_id: null, stage: 'pending' },
  )
})
it('serializes pending synchronization and ignores duplicate submit', async () => {
  await queueOuting(outing)
  const { result } = await ready()
  await act(async () => {
    await result.current.check()
  })
  let release!: () => void
  mocks.send.mockReturnValue(
    new Promise<void>((resolve) => {
      release = resolve
    }),
  )
  let pending!: Promise<boolean>
  await act(async () => {
    pending = result.current.sync([outing.id])
  })
  await waitFor(() => expect(mocks.send).toHaveBeenCalledTimes(1))
  await act(async () => {
    await result.current.sync([outing.id])
  })
  expect(mocks.send).toHaveBeenCalledTimes(1)
  await act(async () => {
    release()
    await pending
  })
})
it('queues local removal and only forgets it after cloud deletion is confirmed', async () => {
  await queueOuting(outing)
  const { result } = await ready()
  await act(async () => {
    await result.current.check()
    await result.current.sync([outing.id])
  })
  // Read the new hook state after the private owner check.
  await act(async () => {
    await result.current.sync([outing.id])
  })
  await act(async () => {
    await result.current.remove(outing.id)
  })
  expect(result.current.records[0].kind).toBe('delete')
  await act(async () => {
    await result.current.sync([outing.id])
  })
  expect(result.current.records).toEqual([])
})
it('clears cloud display and owner when private access is forgotten', async () => {
  const hook = renderHook(({ token }) => useJournal(token, true), {
    initialProps: { token: 'private-memory-token' },
  })
  await waitFor(() => expect(hook.result.current.restoring).toBe(false))
  await act(async () => {
    await hook.result.current.check()
  })
  expect(hook.result.current.status?.owner_id).toBe(owner)
  hook.rerender({ token: '' })
  expect(hook.result.current.status).toBeNull()
  expect(hook.result.current.cloud).toEqual([])
})

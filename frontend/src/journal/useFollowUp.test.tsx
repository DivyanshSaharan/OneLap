import { act, renderHook } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { useFollowUp } from './useFollowUp'
import { mission } from '../test/fixtures'
import { outing, owner } from './test-fixtures'

const mocks = vi.hoisted(() => ({ create: vi.fn(), status: vi.fn() }))
vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  createFollowUp: mocks.create,
  getFollowUpStatus: mocks.status,
}))
const response = {
  reflection: 'Fictional model reflection.',
  mission,
  source_ids: [outing.id],
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.status.mockResolvedValue({
    enabled: true,
    disabled_reason: null,
    data_boundary: 'Fixture only.',
  })
  mocks.create.mockResolvedValue(response)
})

it('captures the generating owner and exact returned source IDs without copying the note', async () => {
  const { result } = renderHook(() => useFollowUp('', true, true))
  await act(async () => {
    await result.current.check()
  })
  await act(async () => {
    await result.current.generate(owner, outing.id, [])
  })
  expect(result.current.suggestion?.origin).toEqual({
    owner_id: owner,
    source_ids: [outing.id],
  })
  expect(JSON.stringify(result.current.suggestion?.origin)).not.toContain(
    outing.observation,
  )
  expect(mocks.create).toHaveBeenCalledExactlyOnceWith('', owner, outing.id, [])
})

it('forgets a pending suggestion and its origin when the connection changes', async () => {
  const { result, rerender } = renderHook(
    ({ token }) => useFollowUp(token, true, true),
    { initialProps: { token: '' } },
  )
  await act(async () => {
    await result.current.check()
  })
  await act(async () => {
    await result.current.generate(owner, outing.id, [])
  })
  rerender({ token: 'different-connection' })
  expect(result.current.suggestion).toBeNull()
  expect(mocks.create).toHaveBeenCalledTimes(1)
})

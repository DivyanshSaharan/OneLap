import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { useMission } from './useMission'
import { mission, status } from '../test/fixtures'
import { otherOwner, outing, owner } from '../journal/test-fixtures'

const mocks = vi.hoisted(() => ({
  load: vi.fn(),
  save: vi.fn(),
  clear: vi.fn(),
  status: vi.fn(),
  generate: vi.fn(),
  journalStatus: vi.fn(),
  loadOwner: vi.fn(),
  saveOwner: vi.fn(),
}))
vi.mock('../storage', async (original) => ({
  ...(await original<typeof import('../storage')>()),
  loadMission: mocks.load,
  saveMission: mocks.save,
  clearMission: mocks.clear,
  loadLocalOwner: mocks.loadOwner,
  saveLocalOwner: mocks.saveOwner,
}))
vi.mock('../journal/api', async (original) => ({
  ...(await original<typeof import('../journal/api')>()),
  getJournalStatus: mocks.journalStatus,
}))
vi.mock('../api', async (original) => ({
  ...(await original<typeof import('../api')>()),
  getStatus: mocks.status,
  generateMission: mocks.generate,
}))

const followUp = {
  ...mission,
  id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  generation: {
    ...mission.generation,
    prompt_version: 'follow-up-v2' as const,
  },
}
const origin = { owner_id: owner, source_ids: [outing.id] }
beforeEach(() => {
  vi.clearAllMocks()
  mocks.load.mockResolvedValue({
    version: 1,
    response: mission,
    savedAt: new Date().toISOString(),
  })
  mocks.save.mockResolvedValue(undefined)
  mocks.clear.mockResolvedValue(undefined)
  mocks.status.mockResolvedValue(status)
  mocks.generate.mockResolvedValue(mission)
  mocks.loadOwner.mockResolvedValue(owner)
  mocks.saveOwner.mockResolvedValue(undefined)
  mocks.journalStatus.mockResolvedValue({
    enabled: true,
    disabled_reason: null,
    owner_id: owner,
    data_boundary: 'Fictional test.',
  })
})

it('restores source references without fetching notes or connecting to the model', async () => {
  mocks.load.mockResolvedValue({
    version: 1,
    response: followUp,
    savedAt: new Date().toISOString(),
    followUpOrigin: origin,
  })
  const { result } = renderHook(useMission)
  await waitFor(() => expect(result.current.restoring).toBe(false))
  expect(result.current.followUpOrigin).toEqual(origin)
  expect(mocks.status).not.toHaveBeenCalled()
  expect(mocks.generate).not.toHaveBeenCalled()
  expect(mocks.load).toHaveBeenCalledWith(owner)
})

it('switches to the verified journal without carrying over the previous mission or source links', async () => {
  mocks.load.mockImplementation(async (scope) =>
    scope === owner
      ? {
          version: 1,
          response: followUp,
          savedAt: new Date().toISOString(),
          followUpOrigin: origin,
        }
      : null,
  )
  mocks.journalStatus.mockResolvedValue({
    enabled: true,
    disabled_reason: null,
    owner_id: otherOwner,
    data_boundary: 'Fictional journal.',
  })
  const { result } = renderHook(useMission)
  await waitFor(() => expect(result.current.restoring).toBe(false))
  expect(result.current.followUpOrigin).toEqual(origin)
  await act(async () => {
    await result.current.connect('different-private-token')
  })
  expect(result.current.owner).toBe(otherOwner)
  expect(result.current.mission).toBeNull()
  expect(result.current.followUpOrigin).toBeNull()
  expect(mocks.saveOwner).toHaveBeenCalledWith(otherOwner)
  await act(async () => {
    expect(await result.current.adoptFollowUp(followUp, origin)).toBe(false)
  })
  expect(mocks.save).not.toHaveBeenCalled()
})

it('forgetting access hides the journal and restores separate device-only data', async () => {
  const deviceMission = {
    ...mission,
    mission: { ...mission.mission, title: 'Device-only mission' },
  }
  mocks.load.mockImplementation(async (scope) => ({
    version: 1,
    response: scope === owner ? followUp : deviceMission,
    savedAt: new Date().toISOString(),
  }))
  const { result } = renderHook(useMission)
  await waitFor(() => expect(result.current.restoring).toBe(false))
  await act(async () => {
    result.current.disconnect()
  })
  await waitFor(() => expect(result.current.busy).toBeNull())
  expect(result.current.owner).toBeNull()
  expect(result.current.mission).toEqual(deviceMission)
  expect(result.current.followUpOrigin).toBeNull()
  expect(mocks.saveOwner).toHaveBeenCalledWith(null)
})

it('atomically accepts the mission with its origin and clears both together', async () => {
  const { result } = renderHook(useMission)
  await waitFor(() => expect(result.current.restoring).toBe(false))
  let accepted = false
  await act(async () => {
    accepted = await result.current.adoptFollowUp(followUp, origin)
  })
  expect(accepted).toBe(true)
  expect(mocks.save).toHaveBeenCalledExactlyOnceWith(
    followUp,
    'generated',
    origin,
    owner,
  )
  expect(result.current.mission).toEqual(followUp)
  expect(result.current.followUpOrigin).toEqual(origin)
  await act(async () => {
    await result.current.clear()
  })
  expect(result.current.mission).toBeNull()
  expect(result.current.followUpOrigin).toBeNull()
})

it('keeps the earlier mission and references when replacing it fails', async () => {
  mocks.load.mockResolvedValue({
    version: 1,
    response: followUp,
    savedAt: new Date().toISOString(),
    followUpOrigin: origin,
  })
  mocks.save.mockRejectedValue(new Error('disk-full'))
  const { result } = renderHook(useMission)
  await waitFor(() => expect(result.current.restoring).toBe(false))
  let accepted = true
  await act(async () => {
    accepted = await result.current.adoptFollowUp(
      { ...followUp, id: mission.id },
      { ...origin, source_ids: ['cccccccc-cccc-4ccc-8ccc-cccccccccccc'] },
    )
  })
  expect(accepted).toBe(false)
  expect(result.current.mission).toEqual(followUp)
  expect(result.current.followUpOrigin).toEqual(origin)
})

it('does not install invalid references even when storage is mocked', async () => {
  const { result } = renderHook(useMission)
  await waitFor(() => expect(result.current.restoring).toBe(false))
  await act(async () => {
    expect(
      await result.current.adoptFollowUp(followUp, {
        ...origin,
        source_ids: [],
      }),
    ).toBe(false)
  })
  expect(mocks.save).not.toHaveBeenCalled()
  expect(result.current.mission).toEqual(mission)
  expect(result.current.followUpOrigin).toBeNull()
})

it('drops stale references after a new generated or imported mission', async () => {
  mocks.load.mockResolvedValue({
    version: 1,
    response: followUp,
    savedAt: new Date().toISOString(),
    followUpOrigin: origin,
  })
  const { result } = renderHook(useMission)
  await waitFor(() => expect(result.current.restoring).toBe(false))
  await act(async () => {
    await result.current.connect('')
  })
  await act(async () => {
    await result.current.generate(mission.mission)
  })
  expect(result.current.followUpOrigin).toBeNull()
  await act(async () => {
    await result.current.adoptFollowUp(followUp, origin)
  })
  await act(async () => {
    await result.current.importMission(mission)
  })
  expect(result.current.followUpOrigin).toBeNull()
  expect(result.current.missionSource).toBe('imported')
})

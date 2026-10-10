import { beforeEach, expect, it } from 'vitest'
import {
  clearMission,
  loadMission,
  saveMission,
  type MissionSource,
  type FollowUpOrigin,
} from './storage'
import { mission } from './test/fixtures'
import { outing, owner } from './journal/test-fixtures'

const followUp = {
  ...mission,
  generation: {
    ...mission.generation,
    prompt_version: 'follow-up-v2' as const,
  },
}
const origin: FollowUpOrigin = { owner_id: owner, source_ids: [outing.id] }

beforeEach(async () => {
  await clearMission()
})

it('loads no mission on an empty device', async () =>
  expect(await loadMission()).toBeNull())
it('preserves imported provenance across reload without changing old record shape', async () => {
  const imported = await saveMission(mission, 'imported')
  expect(imported.source).toBe('imported')
  expect(await loadMission()).toEqual(imported)
  await saveMission(mission)
  expect((await loadMission())?.source).toBeUndefined()
})
it('rejects an invalid source before changing a saved mission', async () => {
  await saveMission(mission, 'imported')
  await expect(
    saveMission(mission, 'verified' as MissionSource),
  ).rejects.toThrow()
  expect((await loadMission())?.source).toBe('imported')
})
it('persists a validated mission and timestamp', async () => {
  const record = await saveMission(mission)
  expect(await loadMission()).toEqual(record)
  expect(Number.isFinite(Date.parse(record.savedAt))).toBe(true)
  expect(Object.keys(record).sort()).toEqual(['response', 'savedAt', 'version'])
})
it('replaces the one saved mission atomically', async () => {
  await saveMission(mission)
  const replacement = { ...mission, id: '11111111-1111-4111-8111-111111111111' }
  await saveMission(replacement)
  expect((await loadMission())?.response.id).toBe(replacement.id)
})
it('clears only the current saved mission', async () => {
  await saveMission(mission)
  await clearMission()
  expect(await loadMission()).toBeNull()
})
it('rejects invalid responses before replacing a valid save', async () => {
  await saveMission(mission)
  await expect(saveMission({ ...mission, id: 'invalid' })).rejects.toThrow()
  expect((await loadMission())?.response).toEqual(mission)
})
it('fails visibly for corrupted stored data instead of inventing a mission', async () => {
  const database = await new Promise<IDBDatabase>((resolve) => {
    const request = indexedDB.open('onelap-local', 2)
    request.onsuccess = () => resolve(request.result)
  })
  await new Promise<void>((resolve) => {
    const transaction = database.transaction('missions', 'readwrite')
    transaction
      .objectStore('missions')
      .put({ version: 1, response: mission, savedAt: 'not-a-date' }, 'current')
    transaction.oncomplete = () => resolve()
  })
  database.close()
  await expect(loadMission()).rejects.toThrow('saved_mission_invalid')
})

it('retains only bounded source references for an accepted follow-up', async () => {
  const saved = await saveMission(followUp, 'generated', origin)
  expect(saved.followUpOrigin).toEqual(origin)
  expect(await loadMission()).toEqual(saved)
  expect(JSON.stringify(saved.followUpOrigin)).not.toContain(outing.observation)
  expect(Object.keys(saved.followUpOrigin!).sort()).toEqual([
    'owner_id',
    'source_ids',
  ])
})

it('copies source IDs instead of retaining a caller-owned mutable array', async () => {
  const mutable = { ...origin, source_ids: [...origin.source_ids] }
  const saved = await saveMission(followUp, 'generated', mutable)
  mutable.source_ids.push('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')
  expect(saved.followUpOrigin).toEqual(origin)
  expect((await loadMission())?.followUpOrigin).toEqual(origin)
})

it.each([
  null,
  { ...origin, owner_id: 'invalid' },
  { ...origin, source_ids: [] },
  { ...origin, source_ids: [outing.id, outing.id] },
  { ...origin, source_ids: ['INVALID'] },
  {
    ...origin,
    source_ids: Array.from({ length: 4 }, (_, index) => `${index}`.repeat(36)),
  },
  { ...origin, observation: 'PRIVATE NOTE' },
  { ...origin, reflection: 'PRIVATE INTERPRETATION' },
])(
  'rejects invalid source metadata without replacing the existing mission: %j',
  async (value) => {
    await saveMission(mission, 'imported')
    await expect(
      saveMission(followUp, 'generated', value as FollowUpOrigin),
    ).rejects.toThrow()
    expect((await loadMission())?.source).toBe('imported')
  },
)

it('does not allow imported files or initial missions to claim follow-up references', async () => {
  await saveMission(followUp, 'generated', origin)
  await expect(saveMission(followUp, 'imported', origin)).rejects.toThrow()
  await expect(saveMission(mission, 'generated', origin)).rejects.toThrow()
  expect((await loadMission())?.followUpOrigin).toEqual(origin)
})

it('removes old references when generating/importing a replacement or clearing the mission', async () => {
  await saveMission(followUp, 'generated', origin)
  await saveMission(mission)
  expect((await loadMission())?.followUpOrigin).toBeUndefined()
  await saveMission(followUp, 'generated', origin)
  await saveMission(followUp, 'imported')
  expect((await loadMission())?.followUpOrigin).toBeUndefined()
  await clearMission()
  expect(await loadMission()).toBeNull()
})

it('opens an old follow-up without inventing missing references', async () => {
  await saveMission(followUp)
  expect((await loadMission())?.followUpOrigin).toBeUndefined()
})

it('rejects corrupted source metadata on read instead of showing it as provenance', async () => {
  const database = await new Promise<IDBDatabase>((resolve) => {
    const request = indexedDB.open('onelap-local', 2)
    request.onsuccess = () => resolve(request.result)
  })
  await new Promise<void>((resolve) => {
    const transaction = database.transaction('missions', 'readwrite')
    transaction.objectStore('missions').put(
      {
        version: 1,
        response: followUp,
        savedAt: new Date().toISOString(),
        followUpOrigin: { ...origin, source_ids: [] },
      },
      'current',
    )
    transaction.oncomplete = () => resolve()
  })
  database.close()
  await expect(loadMission()).rejects.toThrow()
})

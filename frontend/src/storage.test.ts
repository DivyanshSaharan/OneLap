import { beforeEach, expect, it } from 'vitest'
import {
  clearMission,
  loadMission,
  saveMission,
  type MissionSource,
} from './storage'
import { mission } from './test/fixtures'

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

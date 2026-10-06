import { beforeEach, expect, it } from 'vitest'
import { clearMission, loadMission, saveMission } from './storage'
import { mission } from './test/fixtures'

beforeEach(async () => {
  await clearMission()
})

it('loads no mission on an empty device', async () =>
  expect(await loadMission()).toBeNull())
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
    const request = indexedDB.open('onelap-local', 1)
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

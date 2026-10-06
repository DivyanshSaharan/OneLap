import { beforeEach, expect, it, vi } from 'vitest'
import { IDBFactory } from 'fake-indexeddb'
import { loadMission, openDatabase } from '../storage'
import { mission } from '../test/fixtures'
import {
  acknowledge,
  bindForSync,
  loadOutbox,
  queueCloudDeletion,
  queueOuting,
  removeOuting,
} from './outbox'
import { otherOwner, outing, owner } from './test-fixtures'

beforeEach(() => vi.stubGlobal('indexedDB', new IDBFactory()))

it('upgrades version one without deleting the saved mission', async () => {
  const database = await new Promise<IDBDatabase>((resolve) => {
    const request = indexedDB.open('onelap-local', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('missions')
    request.onsuccess = () => resolve(request.result)
  })
  await new Promise<void>((resolve) => {
    const transaction = database.transaction('missions', 'readwrite')
    transaction
      .objectStore('missions')
      .put(
        { version: 1, response: mission, savedAt: outing.recorded_at },
        'current',
      )
    transaction.oncomplete = () => resolve()
  })
  database.close()
  await queueOuting(outing)
  expect((await loadMission())?.response).toEqual(mission)
  expect((await loadOutbox())[0]).toMatchObject({
    kind: 'entry',
    stage: 'pending',
    owner_id: null,
    entry: outing,
  })
})
it('never overwrites an existing entry ID', async () => {
  await queueOuting(outing)
  await expect(
    queueOuting({ ...outing, observation: 'different' }),
  ).rejects.toThrow('outbox_conflict')
  expect((await loadOutbox())[0]).toMatchObject({ entry: outing })
})
it('binds an entry once and refuses reassignment to another journal', async () => {
  await queueOuting(outing)
  await bindForSync(outing.id, owner)
  await expect(bindForSync(outing.id, otherOwner)).rejects.toThrow(
    'journal_owner_mismatch',
  )
  expect((await loadOutbox())[0].owner_id).toBe(owner)
})
it('only marks a confirmed entry as synced for the matching owner', async () => {
  await queueOuting(outing)
  await bindForSync(outing.id, owner)
  await acknowledge(outing.id, otherOwner, 'entry')
  expect((await loadOutbox())[0]).toMatchObject({ stage: 'pending' })
  await acknowledge(outing.id, owner, 'entry')
  expect((await loadOutbox())[0]).toMatchObject({ stage: 'synced' })
})
it('removes never-uploaded unassigned notes locally without a cloud deletion', async () => {
  await queueOuting(outing)
  await removeOuting(outing.id)
  expect(await loadOutbox()).toEqual([])
})
it('replaces a possibly uploaded note with a content-free pending deletion', async () => {
  await queueOuting(outing)
  await bindForSync(outing.id, owner)
  await removeOuting(outing.id)
  expect(await loadOutbox()).toEqual([
    { version: 1, kind: 'delete', id: outing.id, owner_id: owner },
  ])
})
it('a delayed upload acknowledgment cannot erase a newer pending deletion', async () => {
  await queueOuting(outing)
  await bindForSync(outing.id, owner)
  await removeOuting(outing.id)
  await acknowledge(outing.id, owner, 'entry')
  expect((await loadOutbox())[0].kind).toBe('delete')
  await acknowledge(outing.id, owner, 'delete')
  expect(await loadOutbox()).toEqual([])
})
it('deletion from cloud-only history is durable and owner-bound', async () => {
  await queueCloudDeletion(outing.id, owner)
  await expect(queueCloudDeletion(outing.id, otherOwner)).rejects.toThrow(
    'journal_owner_mismatch',
  )
  expect((await loadOutbox())[0]).toEqual({
    version: 1,
    kind: 'delete',
    id: outing.id,
    owner_id: owner,
  })
})
it('does not replace an unassigned local note when queueing a cloud-only deletion', async () => {
  await queueOuting(outing)
  await expect(queueCloudDeletion(outing.id, owner)).rejects.toThrow(
    'journal_owner_mismatch',
  )
  expect((await loadOutbox())[0]).toMatchObject({
    kind: 'entry',
    entry: outing,
  })
})
it('corrupt stored observations fail visibly', async () => {
  const database = await openDatabase()
  await new Promise<void>((resolve) => {
    const transaction = database.transaction('outings', 'readwrite')
    transaction
      .objectStore('outings')
      .put({ id: outing.id, version: 7, kind: 'entry' })
    transaction.oncomplete = () => resolve()
  })
  database.close()
  await expect(loadOutbox()).rejects.toThrow()
})
it('concurrent removal and binding preserve deletion intent', async () => {
  await queueOuting(outing)
  await Promise.all([bindForSync(outing.id, owner), removeOuting(outing.id)])
  const rows = await loadOutbox()
  expect(rows).toHaveLength(1)
  expect(rows[0].kind).toBe('delete')
})

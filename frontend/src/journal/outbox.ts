import { openDatabase } from '../storage'
import {
  identifier,
  parseLocal,
  parseOuting,
  type EntryRecord,
  type LocalRecord,
  type Outing,
} from './domain'

const STORE = 'outings'
export async function loadOutbox(): Promise<LocalRecord[]> {
  const database = await openDatabase()
  try {
    const rows = await new Promise<unknown[]>((resolve, reject) => {
      const request = database
        .transaction(STORE, 'readonly')
        .objectStore(STORE)
        .getAll()
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(new Error('outbox_unavailable'))
    })
    return rows.map(parseLocal)
  } finally {
    database.close()
  }
}

async function mutate(
  id: string,
  operation: (current: LocalRecord | null) => LocalRecord | null,
): Promise<void> {
  if (!identifier(id)) throw new Error('invalid_outbox')
  const database = await openDatabase()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE, 'readwrite')
      const store = transaction.objectStore(STORE)
      let failure: unknown = null
      transaction.oncomplete = () => resolve()
      transaction.onerror = transaction.onabort = () =>
        reject(failure ?? new Error('outbox_unavailable'))
      const request = store.get(id)
      request.onsuccess = () => {
        try {
          const next = operation(
            request.result === undefined ? null : parseLocal(request.result),
          )
          if (next) store.put(parseLocal(next))
          else store.delete(id)
        } catch (error) {
          failure = error
          transaction.abort()
        }
      }
    })
  } finally {
    database.close()
  }
}

export async function queueOuting(entry: Outing): Promise<void> {
  const validated = parseOuting(entry)
  await mutate(entry.id, (current) => {
    if (current) throw new Error('outbox_conflict')
    return {
      version: 1,
      kind: 'entry',
      id: entry.id,
      owner_id: null,
      stage: 'pending',
      entry: validated,
    }
  })
}
export async function bindForSync(
  id: string,
  owner: string,
): Promise<LocalRecord | null> {
  if (!identifier(owner)) throw new Error('invalid_outbox')
  await mutate(id, (current) => {
    if (!current) return null
    if (current.owner_id !== null && current.owner_id !== owner)
      throw new Error('journal_owner_mismatch')
    return { ...current, owner_id: owner }
  })
  return (await loadOutbox()).find((row) => row.id === id) ?? null
}
export async function acknowledge(
  id: string,
  owner: string,
  kind: 'entry' | 'delete',
): Promise<void> {
  await mutate(id, (current) => {
    if (!current || current.owner_id !== owner || current.kind !== kind)
      return current
    return kind === 'delete'
      ? null
      : { ...(current as EntryRecord), stage: 'synced' }
  })
}
export async function removeOuting(id: string): Promise<void> {
  await mutate(id, (current) => {
    if (!current || current.owner_id === null) return null
    return {
      version: 1,
      kind: 'delete',
      id: current.id,
      owner_id: current.owner_id,
    }
  })
}
export async function queueCloudDeletion(
  id: string,
  owner: string,
): Promise<void> {
  if (!identifier(owner)) throw new Error('invalid_outbox')
  await mutate(id, (current) => {
    if (current && current.owner_id !== owner)
      throw new Error('journal_owner_mismatch')
    return { version: 1, kind: 'delete', id, owner_id: owner }
  })
}

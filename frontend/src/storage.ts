import { parseMission, type MissionResponse } from './domain'

const DATABASE = 'onelap-local'
const STORE = 'missions'
const KEY = 'current'
export type MissionSource = 'generated' | 'imported'
export interface SavedMission {
  version: 1
  response: MissionResponse
  savedAt: string
  source?: MissionSource
}

export function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    let blocked = false
    const request = indexedDB.open(DATABASE, 2)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE))
        request.result.createObjectStore(STORE)
      if (!request.result.objectStoreNames.contains('outings'))
        request.result.createObjectStore('outings', { keyPath: 'id' })
    }
    request.onerror = () => reject(new Error('storage_unavailable'))
    request.onblocked = () => {
      blocked = true
      reject(new Error('storage_blocked'))
    }
    request.onsuccess = () => {
      if (blocked) {
        request.result.close()
        return
      }
      request.result.onversionchange = () => request.result.close()
      resolve(request.result)
    }
  })
}

export async function loadMission(): Promise<SavedMission | null> {
  const database = await openDatabase()
  try {
    const value = await new Promise<unknown>((resolve, reject) => {
      const transaction = database.transaction(STORE, 'readonly')
      const request = transaction.objectStore(STORE).get(KEY)
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(new Error('storage_unavailable'))
    })
    if (value === undefined) return null
    if (
      !value ||
      typeof value !== 'object' ||
      !('version' in value) ||
      value.version !== 1 ||
      !('response' in value) ||
      !('savedAt' in value) ||
      typeof value.savedAt !== 'string' ||
      (Object.keys(value).length !== 3 &&
        !(Object.keys(value).length === 4 && 'source' in value)) ||
      ('source' in value &&
        value.source !== 'generated' &&
        value.source !== 'imported') ||
      !Number.isFinite(Date.parse(value.savedAt))
    ) {
      throw new Error('saved_mission_invalid')
    }
    return {
      version: 1,
      response: parseMission(value.response),
      savedAt: value.savedAt,
      ...('source' in value ? { source: value.source as MissionSource } : {}),
    }
  } finally {
    database.close()
  }
}

export async function saveMission(
  response: MissionResponse,
  source: MissionSource = 'generated',
): Promise<SavedMission> {
  if (source !== 'generated' && source !== 'imported')
    throw new Error('saved_mission_invalid')
  const record: SavedMission = {
    version: 1,
    response: parseMission(response),
    savedAt: new Date().toISOString(),
    ...(source === 'imported' ? { source } : {}),
  }
  await write(record)
  return record
}

async function write(record: SavedMission | null): Promise<void> {
  const database = await openDatabase()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE, 'readwrite')
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(new Error('storage_unavailable'))
      transaction.onabort = () => reject(new Error('storage_unavailable'))
      if (record) transaction.objectStore(STORE).put(record, KEY)
      else transaction.objectStore(STORE).delete(KEY)
    })
  } finally {
    database.close()
  }
}

export async function clearMission(): Promise<void> {
  await write(null)
}

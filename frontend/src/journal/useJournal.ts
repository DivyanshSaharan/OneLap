import { useCallback, useEffect, useRef, useState } from 'react'
import type { MissionResponse } from '../domain'
import {
  getJournalPage,
  getJournalStatus,
  journalError,
  sendRecord,
} from './api'
import type {
  CloudRecord,
  Feedback,
  JournalStatus,
  LocalRecord,
  Outcome,
} from './domain'
import {
  acknowledge,
  bindForSync,
  loadOutbox,
  queueCloudDeletion,
  queueOuting,
  removeOuting,
} from './outbox'

export function useJournal(
  token: string,
  online: boolean,
  connected = Boolean(token),
) {
  const [records, setRecords] = useState<LocalRecord[]>([])
  const [cloud, setCloud] = useState<CloudRecord[]>([])
  const [nextAfter, setNextAfter] = useState<string | null>(null)
  const [status, setStatus] = useState<JournalStatus | null>(null)
  const [restoring, setRestoring] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [storageError, setStorageError] = useState<string | null>(null)
  const alive = useRef(true)
  const lock = useRef(false)
  const revision = useRef(0)
  const currentToken = useRef(token)
  currentToken.current = token
  const currentConnection = useRef(connected)
  currentConnection.current = connected

  const refresh = useCallback(async () => {
    const version = ++revision.current
    try {
      const rows = await loadOutbox()
      if (alive.current && version === revision.current) {
        setRecords(rows)
        setStorageError(null)
      }
    } catch {
      if (alive.current)
        setStorageError(
          'Saved observations could not be opened. Further uploads are blocked. Reload or inspect device storage before adding another note.',
        )
    } finally {
      if (alive.current) setRestoring(false)
    }
  }, [])
  useEffect(() => {
    alive.current = true
    void refresh()
    const focused = () => {
      if (!lock.current) void refresh()
    }
    window.addEventListener('focus', focused)
    return () => {
      alive.current = false
      ++revision.current
      window.removeEventListener('focus', focused)
    }
  }, [refresh])
  useEffect(() => {
    setStatus(null)
    setCloud([])
    setNextAfter(null)
    setError(null)
    setMessage(null)
  }, [token, connected])

  async function act(task: () => Promise<void>) {
    if (lock.current || restoring || storageError) return false
    lock.current = true
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await task()
      return true
    } catch (failure) {
      if (alive.current) setError(journalError(failure))
      return false
    } finally {
      await refresh()
      lock.current = false
      if (alive.current) setBusy(false)
    }
  }
  const owner = status?.enabled ? status.owner_id : null
  return {
    records,
    cloud,
    nextAfter,
    status,
    restoring,
    busy,
    error,
    message,
    storageError,
    refresh,
    check: () =>
      act(async () => {
        if (!connected || !online) return
        const result = await getJournalStatus(token)
        if (
          alive.current &&
          currentConnection.current &&
          currentToken.current === token
        )
          setStatus(result)
      }),
    capture: (
      mission: MissionResponse,
      input: { outcome: Outcome; observation: string; feedback: Feedback },
    ) =>
      act(async () => {
        await queueOuting({
          id: crypto.randomUUID(),
          mission,
          ...input,
          observation: input.observation.trim().replace(/\r\n?/g, '\n'),
          recorded_at: new Date().toISOString(),
        })
        if (alive.current)
          setMessage(
            'Observation saved on this device. Not uploaded, and not sent to AI.',
          )
      }),
    sync: (approvedIds: string[]) =>
      act(async () => {
        if (!connected || !online || !owner) return
        const pending = (await loadOutbox()).filter(
          (row) =>
            approvedIds.includes(row.id) &&
            (row.kind === 'delete' || row.stage === 'pending') &&
            (row.owner_id === null || row.owner_id === owner),
        )
        let confirmed = 0
        for (const candidate of pending) {
          if (
            currentToken.current !== token ||
            !currentConnection.current ||
            !alive.current
          )
            break
          const row = await bindForSync(candidate.id, owner)
          if (!row) continue
          await sendRecord(token, owner, row)
          await acknowledge(row.id, owner, row.kind)
          if (row.kind === 'delete' && alive.current)
            setCloud((rows) => rows.filter((item) => item.entry.id !== row.id))
          ++confirmed
        }
        if (alive.current)
          setMessage(
            `${confirmed} journal change${confirmed === 1 ? '' : 's'} confirmed by Atlas. No AI request was made.`,
          )
      }),
    readCloud: (more = false) =>
      act(async () => {
        if (!connected || !online || !owner) return
        const page = await getJournalPage(token, owner, more ? nextAfter : null)
        if (
          alive.current &&
          currentConnection.current &&
          currentToken.current === token
        ) {
          setCloud((rows) =>
            more
              ? [
                  ...rows,
                  ...page.entries.filter(
                    (entry) =>
                      !rows.some((row) => row.entry.id === entry.entry.id),
                  ),
                ]
              : page.entries,
          )
          setNextAfter(page.next_after)
          setMessage(
            'Loaded the cloud journal. Client-submitted missions are not independently verified model outputs.',
          )
        }
      }),
    remove: (id: string) =>
      act(async () => {
        await removeOuting(id)
        if (alive.current)
          setMessage(
            'Removed the local note. If it may exist in Atlas, a content-free deletion is pending your next explicit sync.',
          )
      }),
    removeCloud: (id: string) =>
      act(async () => {
        if (!owner) return
        await queueCloudDeletion(id, owner)
        if (alive.current)
          setMessage(
            'The note is hidden here. Cloud deletion is pending your next explicit sync; it is not yet confirmed.',
          )
      }),
  }
}

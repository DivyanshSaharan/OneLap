import { useCallback, useEffect, useRef, useState } from 'react'
import type { MissionResponse } from '../domain'
import { ApiError } from '../api'
import type { LocalOwner } from '../storage'
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
  localOwner: LocalOwner = null,
) {
  const [records, setRecords] = useState<LocalRecord[]>([])
  const [deviceNotes, setDeviceNotes] = useState<LocalRecord[]>([])
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
  const currentOwner = useRef(localOwner)
  currentOwner.current = localOwner

  const refresh = useCallback(async () => {
    const version = ++revision.current
    try {
      const rows = await loadOutbox(localOwner)
      if (
        alive.current &&
        version === revision.current &&
        currentOwner.current === localOwner
      ) {
        setRecords(rows)
        setStorageError(null)
      }
    } catch {
      if (
        alive.current &&
        version === revision.current &&
        currentOwner.current === localOwner
      )
        setStorageError(
          'Saved observations could not be opened. Further uploads are blocked. Reload or inspect device storage before adding another note.',
        )
    } finally {
      if (
        alive.current &&
        version === revision.current &&
        currentOwner.current === localOwner
      )
        setRestoring(false)
    }
  }, [localOwner])
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
    setDeviceNotes([])
  }, [token, connected, localOwner])

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
      if (
        alive.current &&
        currentOwner.current === localOwner &&
        currentToken.current === token
      )
        setError(journalError(failure))
      return false
    } finally {
      if (currentOwner.current === localOwner) await refresh()
      lock.current = false
      if (alive.current) setBusy(false)
    }
  }
  const owner = status?.enabled ? status.owner_id : null
  const unchanged = () =>
    alive.current &&
    currentToken.current === token &&
    currentConnection.current === connected &&
    currentOwner.current === localOwner
  return {
    records: records.filter((row) => row.owner_id === localOwner),
    deviceNotes:
      status?.owner_id === localOwner && connected ? deviceNotes : [],
    cloud: status?.owner_id === localOwner && connected ? cloud : [],
    nextAfter,
    status: status?.owner_id === localOwner || !status?.enabled ? status : null,
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
        if (result.enabled && result.owner_id !== localOwner)
          throw new ApiError('journal_owner_mismatch')
        if (
          alive.current &&
          currentConnection.current &&
          currentToken.current === token &&
          currentOwner.current === localOwner
        )
          setStatus(result)
      }),
    capture: (
      mission: MissionResponse,
      input: { outcome: Outcome; observation: string; feedback: Feedback },
    ) =>
      act(async () => {
        await queueOuting(
          {
            id: crypto.randomUUID(),
            mission,
            ...input,
            observation: input.observation.trim().replace(/\r\n?/g, '\n'),
            recorded_at: new Date().toISOString(),
          },
          localOwner,
        )
        if (unchanged())
          setMessage(
            'Observation saved on this device. Not uploaded, and not sent to AI.',
          )
      }),
    sync: (approvedIds: string[]) =>
      act(async () => {
        if (!connected || !online || !owner) return
        const pending = (await loadOutbox(localOwner)).filter(
          (row) =>
            approvedIds.includes(row.id) &&
            (row.kind === 'delete' || row.stage === 'pending') &&
            row.owner_id === owner,
        )
        let confirmed = 0
        for (const candidate of pending) {
          if (
            currentToken.current !== token ||
            !currentConnection.current ||
            !alive.current ||
            currentOwner.current !== localOwner
          )
            break
          const row = await bindForSync(candidate.id, owner)
          if (!row || !unchanged()) continue
          await sendRecord(token, owner, row)
          await acknowledge(row.id, owner, row.kind)
          if (row.kind === 'delete' && unchanged())
            setCloud((rows) => rows.filter((item) => item.entry.id !== row.id))
          ++confirmed
        }
        if (unchanged())
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
          currentToken.current === token &&
          currentOwner.current === localOwner
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
        await removeOuting(id, localOwner)
        if (unchanged())
          setMessage(
            'Removed the local note. If it may exist in Atlas, a content-free deletion is pending your next explicit sync.',
          )
      }),
    removeCloud: (id: string) =>
      act(async () => {
        if (!owner) return
        await queueCloudDeletion(id, owner)
        if (unchanged())
          setMessage(
            'The note is hidden here. Cloud deletion is pending your next explicit sync; it is not yet confirmed.',
          )
      }),
    reviewDeviceNotes: () =>
      act(async () => {
        if (!owner || owner !== localOwner || !unchanged()) return
        const rows = await loadOutbox(null)
        if (unchanged()) setDeviceNotes(rows)
      }),
    attachDeviceNotes: (approvedIds: string[]) =>
      act(async () => {
        if (!owner || owner !== localOwner || !unchanged()) return
        const reviewed = new Set(deviceNotes.map((row) => row.id))
        for (const id of approvedIds) {
          if (!reviewed.has(id) || !unchanged()) continue
          const row = (await loadOutbox(null)).find((item) => item.id === id)
          if (row?.kind === 'entry') await bindForSync(id, owner)
        }
        if (unchanged()) {
          setDeviceNotes([])
          setMessage(
            'Selected device-only notes linked to this journal locally. They have not been uploaded or sent to AI.',
          )
        }
      }),
  }
}

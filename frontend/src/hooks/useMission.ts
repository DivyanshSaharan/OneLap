import { useEffect, useRef, useState } from 'react'
import { explain, generateMission, getStatus } from '../api'
import type { MissionRequest, MissionResponse, ProviderStatus } from '../domain'
import { getJournalStatus } from '../journal/api'
import {
  clearMission,
  loadMission,
  loadLocalOwner,
  parseFollowUpOrigin,
  saveMission,
  saveLocalOwner,
  type LocalOwner,
  type FollowUpOrigin,
  type MissionSource,
} from '../storage'

export function useMission() {
  const [restoring, setRestoring] = useState(true)
  const [busy, setBusy] = useState<
    'connecting' | 'generating' | 'saving' | 'clearing' | null
  >(null)
  const lock = useRef(false)
  const alive = useRef(true)
  const [token, setToken] = useState('')
  const [owner, setOwner] = useState<LocalOwner>(null)
  const currentOwner = useRef<LocalOwner>(null)
  const [status, setStatus] = useState<ProviderStatus | null>(null)
  const [mission, setMission] = useState<MissionResponse | null>(null)
  const [missionSource, setMissionSource] = useState<MissionSource>('generated')
  const [followUpOrigin, setFollowUpOrigin] = useState<FollowUpOrigin | null>(
    null,
  )
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [storageError, setStorageError] = useState<string | null>(null)

  useEffect(() => {
    alive.current = true
    let cancelled = false
    loadLocalOwner()
      .then(async (restoredOwner) => {
        const record = await loadMission(restoredOwner)
        if (!cancelled) {
          currentOwner.current = restoredOwner
          setOwner(restoredOwner)
        }
        return record
      })
      .then((record) => {
        if (!cancelled && record) {
          setMission(record.response)
          setMissionSource(record.source ?? 'generated')
          setFollowUpOrigin(record.followUpOrigin ?? null)
          setSaved(true)
        }
      })
      .catch(() => {
        if (!cancelled)
          setStorageError(
            'Saved data could not be opened. Offline access is not ready. You can clear this device’s saved mission and try again.',
          )
      })
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })
    return () => {
      cancelled = true
      alive.current = false
    }
  }, [])

  async function switchOwner(nextOwner: LocalOwner) {
    if (currentOwner.current === nextOwner) return
    const record = await loadMission(nextOwner)
    await saveLocalOwner(nextOwner)
    if (!alive.current) return
    currentOwner.current = nextOwner
    setOwner(nextOwner)
    setMission(record?.response ?? null)
    setMissionSource(record?.source ?? 'generated')
    setFollowUpOrigin(record?.followUpOrigin ?? null)
    setSaved(Boolean(record))
    setStorageError(null)
  }

  async function writeMission(
    response: MissionResponse,
    source: MissionSource,
    origin: FollowUpOrigin | null,
  ) {
    if (origin && origin.owner_id !== currentOwner.current)
      throw new Error('saved_mission_invalid')
    if (currentOwner.current !== null)
      return saveMission(
        response,
        source,
        origin ?? undefined,
        currentOwner.current,
      )
    if (origin) return saveMission(response, source, origin)
    if (source === 'imported') return saveMission(response, source)
    return saveMission(response)
  }

  async function act(
    kind: NonNullable<typeof busy>,
    task: () => Promise<void>,
  ): Promise<boolean> {
    if (lock.current || restoring) return false
    lock.current = true
    setBusy(kind)
    setError(null)
    let succeeded = true
    try {
      await task()
    } catch (failure) {
      succeeded = false
      if (alive.current) {
        setError(explain(failure))
        if (kind === 'generating') {
          setStatus(null)
          setToken('')
        }
      }
    } finally {
      lock.current = false
      if (alive.current) setBusy(null)
    }
    return succeeded
  }

  async function persist(
    response: MissionResponse,
    source: MissionSource = 'generated',
    origin: FollowUpOrigin | null = null,
  ) {
    try {
      await writeMission(response, source, origin)
      if (alive.current) {
        setSaved(true)
        setStorageError(null)
      }
    } catch {
      if (alive.current) {
        setSaved(false)
        setStorageError(
          'Your mission was created, but could not be saved on this device. Keep this page open; offline reopening is not ready.',
        )
      }
    }
  }

  async function replaceMission(
    response: MissionResponse,
    source: MissionSource,
    origin: FollowUpOrigin | null = null,
  ) {
    let accepted = false
    const acted = await act('saving', async () => {
      let validatedOrigin: FollowUpOrigin | null = null
      try {
        if (source === 'generated' && !origin)
          throw new Error('saved_mission_invalid')
        if (origin) {
          validatedOrigin = parseFollowUpOrigin(origin)
          await writeMission(response, source, validatedOrigin)
        } else await writeMission(response, source, null)
      } catch {
        if (alive.current)
          setStorageError(
            'The selected mission could not be saved. Your current mission was kept.',
          )
        return
      }
      if (alive.current) {
        setMission(response)
        setMissionSource(source)
        setFollowUpOrigin(validatedOrigin)
        setSaved(true)
        setStorageError(null)
        setError(null)
        accepted = true
      }
    })
    return acted && accepted
  }

  return {
    restoring,
    busy,
    status,
    mission,
    missionSource,
    followUpOrigin,
    saved,
    error,
    storageError,
    accessToken: token,
    owner,
    connect: async (candidate: string) => {
      await act('connecting', async () => {
        setStatus(null)
        setToken('')
        const result = await getStatus(candidate)
        const journal = await getJournalStatus(candidate)
        await switchOwner(journal.enabled ? journal.owner_id : null)
        if (alive.current) {
          setToken(candidate)
          setStatus(result)
        }
      })
    },
    disconnect: () => {
      void act('connecting', async () => {
        setToken('')
        setStatus(null)
        setError(null)
        // Hide the previous journal immediately, even if local storage fails.
        setMission(null)
        setFollowUpOrigin(null)
        setSaved(false)
        currentOwner.current = null
        setOwner(null)
        await saveLocalOwner(null)
        const record = await loadMission()
        if (alive.current) {
          setMission(record?.response ?? null)
          setMissionSource(record?.source ?? 'generated')
          setFollowUpOrigin(record?.followUpOrigin ?? null)
          setSaved(Boolean(record))
        }
      })
    },
    generate: async (input: MissionRequest) => {
      await act('generating', async () => {
        if (!status?.enabled) return
        const result = await generateMission(token, input)
        if (!alive.current) return
        setMission(result)
        setMissionSource('generated')
        setFollowUpOrigin(null)
        setSaved(false)
        await persist(result)
      })
    },
    adoptFollowUp: (response: MissionResponse, origin: FollowUpOrigin) =>
      replaceMission(response, 'generated', origin),
    importMission: (response: MissionResponse) =>
      replaceMission(response, 'imported'),
    saveAgain: () =>
      act('saving', async () => {
        if (mission) await persist(mission, missionSource, followUpOrigin)
      }),
    clear: () =>
      act('clearing', async () => {
        try {
          if (currentOwner.current !== null)
            await clearMission(currentOwner.current)
          else await clearMission()
        } catch {
          setStorageError(
            'The saved mission could not be removed. It may still be on this device.',
          )
          return
        }
        if (alive.current) {
          setMission(null)
          setMissionSource('generated')
          setFollowUpOrigin(null)
          setSaved(false)
          setStorageError(null)
        }
      }),
  }
}

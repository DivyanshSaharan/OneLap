import { useEffect, useRef, useState } from 'react'
import { explain, generateMission, getStatus } from '../api'
import type { MissionRequest, MissionResponse, ProviderStatus } from '../domain'
import { clearMission, loadMission, saveMission } from '../storage'

export function useMission() {
  const [restoring, setRestoring] = useState(true)
  const [busy, setBusy] = useState<
    'connecting' | 'generating' | 'saving' | 'clearing' | null
  >(null)
  const lock = useRef(false)
  const alive = useRef(true)
  const [token, setToken] = useState('')
  const [status, setStatus] = useState<ProviderStatus | null>(null)
  const [mission, setMission] = useState<MissionResponse | null>(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [storageError, setStorageError] = useState<string | null>(null)

  useEffect(() => {
    alive.current = true
    let cancelled = false
    loadMission()
      .then((record) => {
        if (!cancelled && record) {
          setMission(record.response)
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

  async function act(
    kind: NonNullable<typeof busy>,
    task: () => Promise<void>,
  ) {
    if (lock.current || restoring) return
    lock.current = true
    setBusy(kind)
    setError(null)
    try {
      await task()
    } catch (failure) {
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
  }

  async function persist(response: MissionResponse) {
    try {
      await saveMission(response)
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

  return {
    restoring,
    busy,
    status,
    mission,
    saved,
    error,
    storageError,
    connect: (candidate: string) =>
      act('connecting', async () => {
        setStatus(null)
        setToken('')
        const result = await getStatus(candidate)
        if (alive.current) {
          setToken(candidate)
          setStatus(result)
        }
      }),
    disconnect: () => {
      if (!lock.current) {
        setToken('')
        setStatus(null)
        setError(null)
      }
    },
    generate: (input: MissionRequest) =>
      act('generating', async () => {
        if (!status?.enabled || !token) return
        const result = await generateMission(token, input)
        if (!alive.current) return
        setMission(result)
        setSaved(false)
        await persist(result)
      }),
    saveAgain: () =>
      act('saving', async () => {
        if (mission) await persist(mission)
      }),
    clear: () =>
      act('clearing', async () => {
        try {
          await clearMission()
        } catch {
          setStorageError(
            'The saved mission could not be removed. It may still be on this device.',
          )
          return
        }
        if (alive.current) {
          setMission(null)
          setSaved(false)
          setStorageError(null)
        }
      }),
  }
}

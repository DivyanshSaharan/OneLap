import { useEffect, useRef, useState } from 'react'
import { createFollowUp, getFollowUpStatus, journalError } from './api'
import type { FollowUpStatus, FollowUpSuggestion } from './domain'
import type { FollowUpOrigin, LocalOwner } from '../storage'

export function useFollowUp(
  token: string,
  online: boolean,
  connected: boolean,
  localOwner?: LocalOwner,
) {
  const [status, setStatus] = useState<FollowUpStatus | null>(null)
  const [suggestion, setSuggestion] = useState<
    (FollowUpSuggestion & { origin: FollowUpOrigin }) | null
  >(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const lock = useRef(false)
  const alive = useRef(true)
  const currentToken = useRef(token)
  const currentConnection = useRef(connected)
  currentToken.current = token
  currentConnection.current = connected
  const currentOwner = useRef(localOwner)
  currentOwner.current = localOwner

  useEffect(() => {
    setStatus(null)
    setSuggestion(null)
    setError(null)
    setMessage(null)
  }, [token, connected, localOwner])

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  async function act(task: () => Promise<void>) {
    if (lock.current) return false
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
      lock.current = false
      if (alive.current) setBusy(false)
    }
  }

  return {
    status,
    suggestion:
      localOwner === undefined || suggestion?.origin.owner_id === localOwner
        ? suggestion
        : null,
    busy,
    error,
    message,
    check: () =>
      act(async () => {
        if (!connected || !online) return
        const result = await getFollowUpStatus(token)
        if (
          alive.current &&
          currentConnection.current &&
          currentToken.current === token &&
          currentOwner.current === localOwner
        )
          setStatus(result)
      }),
    generate: (owner: string, sourceId: string, contextIds: string[]) =>
      act(async () => {
        if (
          !connected ||
          !online ||
          !status?.enabled ||
          (localOwner !== undefined && owner !== localOwner)
        )
          return
        const result = await createFollowUp(token, owner, sourceId, contextIds)
        if (
          alive.current &&
          currentConnection.current &&
          currentToken.current === token &&
          currentOwner.current === localOwner
        )
          setSuggestion({
            ...result,
            origin: { owner_id: owner, source_ids: [...result.source_ids] },
          })
      }),
    clear: () => {
      setSuggestion(null)
      setError(null)
      setMessage(null)
    },
    accepted: () => {
      setSuggestion(null)
      setMessage('Next mission saved on this device.')
    },
  }
}

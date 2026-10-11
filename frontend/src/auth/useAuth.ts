import { useEffect, useRef, useState } from 'react'
import { explain, setSessionTransport } from '../api'
import { getSession, login, logout, type Session } from './api'

export function useAuth(
  online: boolean,
  restoring: boolean,
  connectAccount: (owner: string) => Promise<boolean>,
  disconnect: () => Promise<void>,
) {
  const [session, setSession] = useState<Session | null>(null)
  const [authenticated, setAuthenticated] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const callbacks = useRef({ connectAccount, disconnect })
  callbacks.current = { connectAccount, disconnect }
  const alive = useRef(true)
  const locked = useRef(false)
  const version = useRef(0)
  const pendingClear = useRef(false)
  const channel = useRef<BroadcastChannel | null>(null)

  async function apply(next: Session, revision: number, cleared = false) {
    if (!alive.current || revision !== version.current) return
    if (next.enabled && !cleared) await callbacks.current.disconnect()
    if (!alive.current || revision !== version.current) return
    setSessionTransport(next.enabled, next.csrf, next.owner_id)
    setSession(next)
    if (next.owner_id) await callbacks.current.connectAccount(next.owner_id)
    if (alive.current && revision === version.current)
      setAuthenticated(next.enabled && Boolean(next.owner_id))
  }

  async function refresh(clear = false) {
    if (clear) setAuthenticated(false)
    if (clear && (!online || restoring)) {
      ++version.current
      setSession(null)
      setSessionTransport(true, null, null)
      void callbacks.current.disconnect()
    }
    if (!online || restoring) return
    if (locked.current) {
      if (clear) {
        pendingClear.current = true
        ++version.current
        setSession(null)
        setSessionTransport(true, null, null)
        void callbacks.current.disconnect()
      }
      return
    }
    locked.current = true
    const revision = ++version.current
    setAuthenticated(false)
    setBusy(true)
    setError(null)
    try {
      if (clear) {
        setSession(null)
        setSessionTransport(true, null, null)
        await callbacks.current.disconnect()
      }
      await apply(await getSession(), revision, clear)
    } catch (failure) {
      if (alive.current && revision === version.current)
        setError(explain(failure))
    } finally {
      locked.current = false
      if (alive.current) setBusy(false)
      if (
        alive.current &&
        (pendingClear.current || revision !== version.current)
      ) {
        pendingClear.current = false
        void refresh(true)
      }
    }
  }

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      ++version.current
    }
  }, [])

  useEffect(() => {
    if (!restoring && online) void refresh()
    // Callbacks use refs; mission/status changes must not trigger another refresh.
  }, [online, restoring])

  useEffect(() => {
    const expired = () => {
      void refresh(true)
    }
    window.addEventListener('onelap:session-expired', expired)
    if (typeof BroadcastChannel !== 'undefined') {
      channel.current = new BroadcastChannel('onelap-account')
      channel.current.onmessage = expired
    }
    return () => {
      window.removeEventListener('onelap:session-expired', expired)
      channel.current?.close()
      channel.current = null
    }
  }, [online, restoring])

  return {
    session,
    authenticated,
    busy,
    error,
    refresh: () => refresh(true),
    finish: async (credential: string, csrf: string) => {
      if (locked.current || !online) return false
      locked.current = true
      const revision = ++version.current
      setAuthenticated(false)
      setBusy(true)
      setError(null)
      try {
        const next = await login(credential, csrf)
        if (!next.owner_id) throw new Error('invalid_response')
        await callbacks.current.disconnect()
        await apply(next, revision, true)
        channel.current?.postMessage('changed')
        return true
      } catch (failure) {
        if (alive.current) setError(explain(failure))
        return false
      } finally {
        locked.current = false
        if (alive.current) setBusy(false)
        if (alive.current && pendingClear.current) {
          pendingClear.current = false
          void refresh(true)
        }
      }
    },
    signOut: async () => {
      if (locked.current || !online) return
      locked.current = true
      ++version.current
      setAuthenticated(false)
      setBusy(true)
      setError(null)
      try {
        // Hide local account UI even when network revocation cannot be confirmed.
        await callbacks.current.disconnect()
        await logout()
        setSessionTransport(true, null, null)
        if (alive.current)
          setSession({ ...session!, owner_id: null, csrf: null })
        window.google?.accounts.id.disableAutoSelect()
        channel.current?.postMessage('changed')
      } catch (failure) {
        if (alive.current)
          setError('Sign-out was not confirmed. ' + explain(failure))
      } finally {
        locked.current = false
        if (alive.current) setBusy(false)
        if (alive.current && pendingClear.current) {
          pendingClear.current = false
          void refresh(true)
        }
      }
    },
  }
}

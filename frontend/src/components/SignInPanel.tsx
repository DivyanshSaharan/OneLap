import { useEffect, useRef, useState } from 'react'
import { explain } from '../api'
import { getChallenge } from '../auth/api'
import { loadGoogle } from '../auth/google'
import type { useAuth } from '../auth/useAuth'
import { Notice } from './Notice'

export function SignInPanel({
  auth,
  busy,
  online,
  connected,
  onConnect,
}: {
  auth: ReturnType<typeof useAuth>
  busy: boolean
  online: boolean
  connected: boolean
  onConnect: (owner: string) => Promise<boolean>
}) {
  const container = useRef<HTMLDivElement>(null)
  const alive = useRef(true)
  const preparing = useRef(false)
  const [loading, setLoading] = useState(false)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const revision = useRef(0)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      ++revision.current
      window.clearTimeout(timer.current)
    }
  }, [])
  useEffect(() => {
    ++revision.current
    container.current?.replaceChildren()
    setReady(false)
    window.clearTimeout(timer.current)
  }, [auth.session?.owner_id])

  async function prepare() {
    if (preparing.current || busy || !online || !auth.session?.client_id) return
    preparing.current = true
    const version = ++revision.current
    setLoading(true)
    setError(null)
    try {
      const google = await loadGoogle()
      const challenge = await getChallenge()
      if (!alive.current || version !== revision.current || !container.current)
        return
      let used = false
      google.initialize({
        client_id: auth.session.client_id,
        nonce: challenge.nonce,
        ux_mode: 'popup',
        auto_select: false,
        callback: (result) => {
          if (!alive.current || version !== revision.current || used) return
          used = true
          setReady(false)
          window.clearTimeout(timer.current)
          container.current?.replaceChildren()
          void auth.finish(result.credential, challenge.csrf)
        },
      })
      container.current.replaceChildren()
      google.renderButton(container.current, {
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        width: 260,
      })
      setReady(true)
      window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => {
        ++revision.current
        container.current?.replaceChildren()
        setReady(false)
        setError('This sign-in attempt expired. Start again when ready.')
      }, 290_000)
    } catch (failure) {
      if (alive.current) setError(explain(failure))
    } finally {
      preparing.current = false
      if (alive.current) setLoading(false)
    }
  }

  return (
    <section className="sign-in-panel" aria-label="Account">
      {auth.session?.owner_id ? (
        <>
          <p className="small">
            {auth.authenticated
              ? 'Signed in with Google · your own journal'
              : 'Your workspace is locked.'}
          </p>
          {!connected && auth.authenticated && (
            <button
              className="secondary-button"
              disabled={busy || !online}
              onClick={() => void onConnect(auth.session!.owner_id!)}
            >
              Reconnect my journal
            </button>
          )}
          <button
            className="text-button"
            disabled={busy || !online}
            onClick={() => void auth.signOut()}
          >
            Sign out
          </button>
        </>
      ) : auth.session?.enabled ? (
        <>
          <p className="small">
            Sign in to use OneLap and keep your journal separate from everyone
            else’s.
          </p>
          {!ready && (
            <button
              className="secondary-button"
              disabled={busy || loading || !online}
              onClick={() => void prepare()}
            >
              {loading ? 'Preparing sign-in…' : 'Sign in with Google'}
            </button>
          )}
          <div ref={container} hidden={!ready || busy || !online} />
          <p className="small muted">
            Sign-in opens Google’s login widget and stores a minimal session in
            Atlas. It does not upload observations or call the model.
          </p>
        </>
      ) : (
        <>
          <p className="small">
            {auth.busy
              ? 'Checking sign-in…'
              : 'Connect to check sign-in availability.'}
          </p>
          <button
            className="secondary-button"
            disabled={busy || !online}
            onClick={() => void auth.refresh()}
          >
            Check sign-in
          </button>
        </>
      )}
      {(auth.error || error) && <Notice error>{auth.error || error}</Notice>}
      <p className="small muted">
        Saved notes remain on this device after sign-out. They are not
        encrypted; avoid shared browsers.
      </p>
    </section>
  )
}

import { useEffect, useState } from 'react'
import { ApiError, explain } from '../api'
import type { ProviderStatus } from '../domain'

interface Props {
  status: ProviderStatus | null
  busy: boolean
  connecting: boolean
  online: boolean
  onConnect: (token: string) => Promise<void>
  onDisconnect: () => void
}

export function AccessPanel({
  status,
  busy,
  connecting,
  online,
  onConnect,
  onDisconnect,
}: Props) {
  const [candidate, setCandidate] = useState('')
  useEffect(() => {
    if (status) setCandidate('')
  }, [status])
  return (
    <details className="access-panel">
      <summary>
        <span>Backend connection</span>
        <span className="access-state">
          {status
            ? status.enabled
              ? 'Ready'
              : 'Connected · generation off'
            : 'Connect to generate'}
        </span>
      </summary>
      <div className="access-content">
        {status ? (
          <>
            <p className="small">
              {status.model} ·{' '}
              {status.target === 'adapter' ? 'trained adapter' : 'base model'} ·
              Tinker
            </p>
            {!status.enabled && (
              <p className="small">
                {explain(
                  new ApiError(status.disabled_reason ?? 'invalid_response'),
                )}
              </p>
            )}
            <p className="small">
              Estimated reservations: $
              {status.estimated_reserved_usd.toFixed(4)} of $
              {status.approved_budget_usd.toFixed(2)} approved. This is not a
              billing balance.
            </p>
            <button
              className="text-button"
              type="button"
              disabled={busy}
              onClick={onDisconnect}
            >
              Disconnect
            </button>
          </>
        ) : (
          <>
            <p className="small muted">
              Connect to check mission and journal availability. This does not
              generate a mission or upload notes.
            </p>
            <button
              className="secondary-button"
              type="button"
              disabled={busy || !online}
              onClick={() => void onConnect('')}
            >
              {connecting ? 'Checking…' : 'Connect to local backend'}
            </button>
            <details>
              <summary>Protected server (optional)</summary>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  if (!busy && online && candidate.trim())
                    void onConnect(candidate.trim())
                }}
              >
                <label htmlFor="access-token">Server access token</label>
                <div className="access-row">
                  <input
                    id="access-token"
                    type="password"
                    value={candidate}
                    onChange={(event) => setCandidate(event.target.value)}
                    autoComplete="off"
                    autoCapitalize="none"
                    spellCheck={false}
                    disabled={busy}
                    placeholder="Enter your private access token"
                  />
                  <button
                    className="secondary-button"
                    type="submit"
                    disabled={busy || !online || !candidate.trim()}
                  >
                    {connecting ? 'Checking…' : 'Connect'}
                  </button>
                </div>
              </form>
            </details>
          </>
        )}
        <p className="small muted">
          Access is forgotten on reload. Your last journal is remembered for
          offline reading. Disconnect keeps notes here, in separate journals.
          This is not sign-in; anyone using this browser can read local notes.
        </p>
        <p className="small muted">
          Generation sends generic outing selections to Tinker. No location,
          photos or audio are collected here.
        </p>
      </div>
    </details>
  )
}

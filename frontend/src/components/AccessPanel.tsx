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
        <span>Private access</span>
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
            <p className="small">{status.model} · base model · Tinker</p>
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
              Forget access
            </button>
          </>
        ) : (
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
        )}
        <p className="small muted">
          Access stays in memory and is forgotten on reload. A saved mission
          remains on this device until you clear it.
        </p>
        <p className="small muted">
          Generation sends generic outing selections to Tinker. No location,
          photos or audio are collected here.
        </p>
      </div>
    </details>
  )
}

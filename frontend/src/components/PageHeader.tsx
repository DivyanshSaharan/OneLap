import type { ReactNode } from 'react'

export function PageHeader({
  online,
  account,
}: {
  online: boolean
  account?: ReactNode
}) {
  return (
    <header className="page-header">
      <a className="brand" href="/" aria-label="OneLap home">
        <img src="/icon.svg" width="38" height="38" alt="" />
        <span>OneLap</span>
      </a>
      <div className="header-actions">
        {(!account || !online) && (
          <span className={`connection ${online ? '' : 'offline'}`}>
            <span aria-hidden="true" className="connection-dot" />
            {online ? 'Network available' : 'Device offline'}
          </span>
        )}
        {account}
      </div>
    </header>
  )
}

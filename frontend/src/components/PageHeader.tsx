export function PageHeader({ online }: { online: boolean }) {
  return (
    <header className="page-header">
      <a className="brand" href="/" aria-label="OneLap home">
        <img src="/icon.svg" width="38" height="38" alt="" />
        <span>OneLap</span>
      </a>
      <span className={`connection ${online ? '' : 'offline'}`}>
        <span aria-hidden="true" className="connection-dot" />
        {online ? 'Network available' : 'Device offline'}
      </span>
    </header>
  )
}

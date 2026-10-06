export function Notice({
  children,
  error = false,
}: {
  children: React.ReactNode
  error?: boolean
}) {
  return (
    <p
      className={`notice ${error ? 'notice-error' : ''}`}
      role={error ? 'alert' : 'status'}
    >
      {children}
    </p>
  )
}

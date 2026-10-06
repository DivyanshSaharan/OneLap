export function EmptyMission({
  busy,
  restoring,
}: {
  busy: boolean
  restoring: boolean
}) {
  return (
    <section
      className="empty-mission panel"
      aria-labelledby="empty-title"
      aria-live="polite"
    >
      <span className="eyebrow">02 / READ, THEN POCKET</span>
      <div className="lap-art" aria-hidden="true">
        <span />
        <span />
        <span />
        <i />
      </div>
      <h2 id="empty-title">
        {restoring
          ? 'Opening your saved lap…'
          : busy
            ? 'A small mission is taking shape.'
            : 'Your outing starts here.'}
      </h2>
      <p>
        {restoring
          ? 'Checking this device, not the model.'
          : busy
            ? 'Waiting for the checked model response. We won’t send another request automatically.'
            : 'No route to plan. No streak to protect. Just a small reason to step outside.'}
      </p>
      <span className="quiet-label">A little noticing goes a long way.</span>
    </section>
  )
}

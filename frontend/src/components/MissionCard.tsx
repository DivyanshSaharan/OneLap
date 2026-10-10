import { memo, useEffect, useRef } from 'react'
import { settingLabels, type MissionResponse } from '../domain'
import type { FollowUpOrigin } from '../storage'

interface Props {
  response: MissionResponse
  imported?: boolean
  followUpOrigin?: FollowUpOrigin | null
  saved: boolean
  offlineReady: boolean
  busy: boolean
  pocket: boolean
  focusOnCreate: boolean
  onPocket: () => void
  onClear: () => void
  onSave: () => void
}

export const MissionCard = memo(function MissionCard({
  response,
  imported = false,
  followUpOrigin = null,
  saved,
  offlineReady,
  busy,
  pocket,
  focusOnCreate,
  onPocket,
  onClear,
  onSave,
}: Props) {
  const mission = response.mission
  const heading = useRef<HTMLHeadingElement>(null)
  const seen = useRef<string | null>(null)
  useEffect(() => {
    const changed = seen.current !== response.id
    seen.current = response.id
    if (changed && focusOnCreate) heading.current?.focus()
  }, [response.id, focusOnCreate])
  return (
    <article
      className={`mission-card panel ${pocket ? 'pocket-card' : ''}`}
      aria-labelledby="mission-title"
    >
      <div className="card-heading">
        <span className="eyebrow">
          {pocket ? 'YOUR SMALL OUTING' : '02 / READ, THEN POCKET'}
        </span>
        <span className="duration">{mission.minutes} min</span>
      </div>
      <h2 id="mission-title" ref={heading} tabIndex={-1}>
        {mission.title}
      </h2>
      {imported && (
        <p className="import-provenance">
          Imported file · model provenance not verified
        </p>
      )}
      <p className="mission-instruction">{mission.instruction}</p>
      <div className="reflection">
        <span className="eyebrow">BRING BACK ONE THOUGHT</span>
        <p>{mission.remember}</p>
      </div>
      <p className="mission-setting">
        {settingLabels[mission.setting]} ·{' '}
        {mission.conditions === 'daylight' ? 'Daylight' : 'Evening'} · No camera
        needed
      </p>
      <p className="save-state" role="status">
        {offlineReady
          ? 'Saved on this device · ready to reopen offline'
          : saved
            ? 'Saved on this device · offline shell not ready yet'
            : 'Not saved yet · keep this page open'}
      </p>
      {!saved && (
        <button className="secondary-button" disabled={busy} onClick={onSave}>
          Try saving again
        </button>
      )}
      {!pocket && (
        <button
          className="primary-button pocket-button"
          disabled={busy}
          onClick={onPocket}
        >
          I’m heading out <span aria-hidden="true">↗</span>
        </button>
      )}
      <p className="safety-note">{response.safety_note}</p>
      {!pocket && (
        <details className="model-details">
          <summary>How this was generated</summary>
          <p className="small">
            {imported && 'The imported file claims: '}
            {response.generation.model} · {response.generation.target} ·{' '}
            {response.generation.provider} ·{' '}
            {response.generation.prompt_version}. Saved locally; not a verified
            account of your surroundings.
          </p>
          {!imported && followUpOrigin && (
            <div
              className="mission-origin"
              aria-label="Saved follow-up source references"
            >
              <p className="small">
                Based on {followUpOrigin.source_ids.length} selected journal{' '}
                {followUpOrigin.source_ids.length === 1 ? 'entry' : 'entries'}.
                References only; no copies of note text or the reflection are
                saved here.
              </p>
              <dl className="small">
                <dt>Journal reference</dt>
                <dd>{followUpOrigin.owner_id}</dd>
                {followUpOrigin.source_ids.map((id, index) => (
                  <div key={id}>
                    <dt>
                      {index === 0
                        ? 'Main observation reference'
                        : `Earlier context reference ${index}`}
                    </dt>
                    <dd>{id}</dd>
                  </div>
                ))}
              </dl>
              <p className="small muted">
                These notes may have been removed or belong to a different
                journal. Opening this section does not fetch them or verify the
                model’s interpretation.
              </p>
            </div>
          )}
          {!imported &&
            !followUpOrigin &&
            response.generation.prompt_version !== 'mission-v1' && (
              <p className="small muted">
                Source references were not saved for this mission.
              </p>
            )}
        </details>
      )}
      <button
        className="text-button clear-button"
        disabled={busy}
        onClick={onClear}
      >
        Clear this device’s saved mission
      </button>
    </article>
  )
})

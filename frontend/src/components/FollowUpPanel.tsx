import { useState } from 'react'
import type { MissionResponse } from '../domain'
import type { FollowUpOrigin } from '../storage'
import { journalReasons } from '../journal/api'
import type { useFollowUp } from '../journal/useFollowUp'
import type { Outing } from '../journal/domain'
import { Notice } from './Notice'

interface Props {
  followUp: ReturnType<typeof useFollowUp>
  entries: Outing[]
  owner: string | null
  busy: boolean
  connected: boolean
  online: boolean
  onAccept: (
    mission: MissionResponse,
    origin: FollowUpOrigin,
  ) => Promise<boolean>
}

function excerpt(value: string) {
  return value.length > 84 ? value.slice(0, 81) + '…' : value
}

function ReviewedEntry({
  entry,
  primary,
}: {
  entry: Outing
  primary: boolean
}) {
  const mission = entry.mission.mission
  return (
    <article className="followup-reviewed-entry">
      <h4>{primary ? 'Main observation' : 'Earlier context'}</h4>
      <dl>
        <div>
          <dt>Recorded (not sent to Qwen)</dt>
          <dd>{new Date(entry.recorded_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Outcome</dt>
          <dd>{entry.outcome}</dd>
        </div>
        <div>
          <dt>Feedback</dt>
          <dd>{entry.feedback?.replaceAll('_', ' ') ?? 'not rated'}</dd>
        </div>
        <div>
          <dt>Mission summary sent</dt>
          <dd>
            {mission.title} — {mission.instruction} ({mission.minutes} minutes;{' '}
            {mission.setting}; {mission.conditions}; {mission.focus})
          </dd>
        </div>
      </dl>
      <p className="observation-text">{entry.observation}</p>
    </article>
  )
}

export function FollowUpPanel({
  followUp,
  entries,
  owner,
  busy,
  connected,
  online,
  onAccept,
}: Props) {
  const [sourceId, setSourceId] = useState('')
  const [contextIds, setContextIds] = useState<string[]>([])
  const [consent, setConsent] = useState(false)
  const byId = new Map(entries.map((entry) => [entry.id, entry]))
  const source = byId.get(sourceId)
  const eligible = entries.filter(
    (entry) => entry.outcome === 'completed' && entry.observation.trim(),
  )
  const readiness = followUp.status
  const priorEntries = source
    ? eligible.filter(
        (entry) =>
          entry.id !== source.id && entry.recorded_at < source.recorded_at,
      )
    : []
  const contexts = contextIds.flatMap((id) => {
    const entry = priorEntries.find((candidate) => candidate.id === id)
    return entry ? [entry] : []
  })
  const enabled =
    Boolean(readiness?.enabled) &&
    Boolean(source) &&
    Boolean(owner) &&
    connected &&
    online

  return (
    <div className="followup-panel">
      <h3>Reflect and choose what comes next.</h3>
      <p className="small muted">
        Pick one completed outing and up to two earlier notes. The server checks
        these records in Atlas before sending them to Qwen.
      </p>
      {followUp.error && <Notice error>{followUp.error}</Notice>}
      {followUp.message && <Notice>{followUp.message}</Notice>}
      <button
        className="secondary-button"
        disabled={busy || !connected || !online}
        onClick={() => void followUp.check()}
      >
        {followUp.busy ? 'Checking…' : 'Check follow-up availability'}
      </button>
      {readiness && (
        <p className="small muted" role="status">
          {readiness.enabled
            ? 'Model and journal settings are enabled. This check does not verify the selected Atlas records.'
            : (journalReasons[readiness.disabled_reason ?? ''] ??
              'Follow-up is not available with the current server settings.')}
        </p>
      )}
      {!eligible.length ? (
        <p className="small muted">
          Sync a completed observation to Atlas first, then load the cloud
          journal here.
        </p>
      ) : (
        <>
          <label>
            Observation to reflect on
            <select
              value={sourceId}
              disabled={busy}
              onChange={(event) => {
                setSourceId(event.target.value)
                setContextIds([])
                setConsent(false)
                followUp.clear()
              }}
            >
              <option value="">Choose a saved observation</option>
              {eligible.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {new Date(entry.recorded_at).toLocaleDateString()} ·{' '}
                  {entry.feedback?.replaceAll('_', ' ') ?? 'not rated'} ·{' '}
                  {excerpt(entry.observation)}
                </option>
              ))}
            </select>
          </label>
          {source && (
            <div
              className="followup-review"
              aria-label="Selected data for review"
            >
              <p className="small">
                Review every selected note below. The listed outcome, feedback,
                observation and mission summary will be read from Atlas and sent
                to Qwen for this request. Record dates and IDs are not sent to
                Qwen.
              </p>
              <ReviewedEntry entry={source} primary />
              {contexts.map((entry) => (
                <ReviewedEntry key={entry.id} entry={entry} primary={false} />
              ))}
            </div>
          )}
          {source && priorEntries.length > 0 && (
            <fieldset className="followup-context" disabled={busy || !source}>
              <legend>Optional context (choose up to two earlier notes)</legend>
              {priorEntries.map((entry) => {
                const checked = contextIds.includes(entry.id)
                return (
                  <label className="followup-context-item" key={entry.id}>
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={!checked && contexts.length >= 2}
                      onChange={(event) => {
                        setContextIds((current) => {
                          const active = current.filter((id) =>
                            priorEntries.some(
                              (candidate) => candidate.id === id,
                            ),
                          )
                          return event.target.checked
                            ? [...active, entry.id]
                            : active.filter((id) => id !== entry.id)
                        })
                        setConsent(false)
                        followUp.clear()
                      }}
                    />
                    <span>
                      {new Date(entry.recorded_at).toLocaleDateString()} ·{' '}
                      {entry.feedback?.replaceAll('_', ' ') ?? 'not rated'} ·{' '}
                      {excerpt(entry.observation)}
                    </span>
                  </label>
                )
              })}
            </fieldset>
          )}
          {source && (
            <div className="followup-sharing">
              <p className="small">
                This request will send the selected observation, feedback and
                mission summaries to hosted Qwen through Tinker. The server
                reads the selected records from Atlas. One model request will
                use the configured spending reservation.
              </p>
              <label className="consent">
                <input
                  type="checkbox"
                  checked={consent}
                  disabled={busy || !enabled}
                  onChange={(event) => {
                    setConsent(event.target.checked)
                    followUp.clear()
                  }}
                />
                <span>
                  I approve sending this selected history for one reflection and
                  next mission.
                </span>
              </label>
              <button
                className="primary-button"
                disabled={busy || !enabled || !consent}
                onClick={() => {
                  setConsent(false)
                  void followUp.generate(
                    owner!,
                    sourceId,
                    contexts.map((entry) => entry.id),
                  )
                }}
              >
                {followUp.busy
                  ? 'Creating your follow-up…'
                  : 'Reflect and suggest a mission'}
              </button>
            </div>
          )}
          {followUp.suggestion && (
            <article className="followup-suggestion" aria-live="polite">
              <span className="eyebrow">MODEL-GENERATED REFLECTION</span>
              <p>{followUp.suggestion.reflection}</p>
              <h4>{followUp.suggestion.mission.mission.title}</h4>
              <p>{followUp.suggestion.mission.mission.instruction}</p>
              <p className="small muted">
                Remember: {followUp.suggestion.mission.mission.remember}
              </p>
              <p className="small muted">
                Based on {followUp.suggestion.source_ids.length} selected{' '}
                {followUp.suggestion.source_ids.length === 1
                  ? 'journal entry'
                  : 'journal entries'}
                . Review before saving.
              </p>
              <div className="journal-actions">
                <button
                  className="primary-button"
                  disabled={busy}
                  onClick={async () => {
                    if (
                      await onAccept(
                        followUp.suggestion!.mission,
                        followUp.suggestion!.origin,
                      )
                    )
                      followUp.accepted()
                  }}
                >
                  Use this next mission
                </button>
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => followUp.clear()}
                >
                  Discard suggestion
                </button>
              </div>
            </article>
          )}
        </>
      )}
    </div>
  )
}

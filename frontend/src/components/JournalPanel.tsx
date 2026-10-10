import { useEffect, useRef, useState } from 'react'
import type { MissionResponse } from '../domain'
import type { FollowUpOrigin } from '../storage'
import { journalReasons } from '../journal/api'
import type { Feedback, Outcome, Outing } from '../journal/domain'
import type { useJournal } from '../journal/useJournal'
import type { useFollowUp } from '../journal/useFollowUp'
import { FollowUpPanel } from './FollowUpPanel'
import { Notice } from './Notice'

interface Props {
  journal: ReturnType<typeof useJournal>
  followUp: ReturnType<typeof useFollowUp>
  mission: MissionResponse | null
  busy: boolean
  connected: boolean
  online: boolean
  returning: number
  onAccept: (
    mission: MissionResponse,
    origin: FollowUpOrigin,
  ) => Promise<boolean>
}
export function JournalPanel({
  journal,
  followUp,
  mission,
  busy,
  connected,
  online,
  returning,
  onAccept,
}: Props) {
  const [outcome, setOutcome] = useState<Outcome>('completed')
  const [feedback, setFeedback] = useState<Feedback>(null)
  const [observation, setObservation] = useState('')
  const [draftMission, setDraftMission] = useState<MissionResponse | null>(
    mission,
  )
  const forMission = draftMission ?? mission
  useEffect(() => {
    if (!observation && outcome === 'completed' && feedback === null)
      setDraftMission(mission)
  }, [mission, observation, outcome, feedback])
  const [consent, setConsent] = useState(false)
  const [approvedIds, setApprovedIds] = useState<string[]>([])
  const [confirming, setConfirming] = useState<string | null>(null)
  const details = useRef<HTMLDetailsElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    if (returning && details.current) {
      details.current.open = true
      textarea.current?.focus()
    }
  }, [returning])
  useEffect(() => {
    setConsent(false)
    setApprovedIds([])
    setConfirming(null)
  }, [journal.status?.owner_id, journal.records])
  const ready = journal.status?.enabled && connected && online
  const localIds = new Set(journal.records.map((row) => row.id))
  const otherOwners = journal.records.some(
    (row) => row.owner_id !== null && row.owner_id !== journal.status?.owner_id,
  )
  const visible = [
    ...journal.records
      .filter((row) => row.kind === 'entry')
      .map((row) => ({
        entry: row.entry,
        state:
          row.stage === 'synced'
            ? 'Saved in Atlas and on this device'
            : 'Saved locally · upload pending',
        local: true,
      })),
    ...journal.cloud
      .filter((row) => !localIds.has(row.entry.id))
      .map((row) => ({
        entry: row.entry,
        state: 'Loaded from Atlas · client-submitted mission',
        local: false,
      })),
  ].sort((a, b) => b.entry.recorded_at.localeCompare(a.entry.recorded_at))
  const syncedLocal = journal.records.flatMap((row) =>
    row.kind === 'entry' &&
    row.stage === 'synced' &&
    row.owner_id === journal.status?.owner_id
      ? [row.entry]
      : [],
  )
  const followUpEntries: Outing[] = [
    ...syncedLocal,
    ...journal.cloud
      // A local tombstone or pending version must not expose a stale cloud copy
      // as an eligible prompt source.
      .filter((row) => !localIds.has(row.entry.id))
      .map((row) => row.entry),
  ].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at))
  return (
    <section className="journal panel" aria-labelledby="journal-title">
      <span className="eyebrow">03 / WHEN YOU’RE BACK</span>
      <h2 id="journal-title">Bring back one thought.</h2>
      <p className="muted">
        No GPS check or proof of completion. Your observation is yours, not the
        model’s interpretation.
      </p>
      {journal.error && <Notice error>{journal.error}</Notice>}
      {journal.storageError && (
        <Notice error>
          {journal.storageError}{' '}
          <button
            className="text-button"
            disabled={busy}
            onClick={() => void journal.refresh()}
          >
            Reload saved observations
          </button>
        </Notice>
      )}
      {journal.message && <Notice>{journal.message}</Notice>}
      <details className="observation-details" ref={details}>
        <summary>Record an observation</summary>
        <form
          onSubmit={async (event) => {
            event.preventDefault()
            if (
              busy ||
              !forMission ||
              (outcome === 'completed' && !observation.trim())
            )
              return
            const saved = await journal.capture(forMission, {
              outcome,
              observation,
              feedback,
            })
            if (saved) {
              setObservation('')
              setFeedback(null)
              setOutcome('completed')
              setDraftMission(mission)
            }
          }}
        >
          <p className="small muted">
            {forMission
              ? `For: ${forMission.mission.title}`
              : 'Create or restore a mission first.'}
          </p>
          {forMission && mission && forMission.id !== mission.id && (
            <p className="small muted">
              This draft still belongs to the earlier mission shown above.
            </p>
          )}
          <fieldset
            disabled={busy || !forMission || Boolean(journal.storageError)}
            className="journal-fields"
          >
            <legend className="sr-only">Your outing feedback</legend>
            <div className="field-grid">
              <label>
                How did the outing go?
                <select
                  value={outcome}
                  onChange={(event) =>
                    setOutcome(event.target.value as Outcome)
                  }
                >
                  <option value="completed">I completed it</option>
                  <option value="stopped">I stopped</option>
                  <option value="skipped">I skipped it</option>
                </select>
              </label>
              <label>
                How did the mission fit?
                <select
                  value={feedback ?? ''}
                  onChange={(event) =>
                    setFeedback((event.target.value || null) as Feedback)
                  }
                >
                  <option value="">Not rated</option>
                  <option value="useful">Useful</option>
                  <option value="too_difficult">Too difficult</option>
                  <option value="not_for_me">Not for me</option>
                </select>
              </label>
            </div>
            <label>
              What did you notice?
              <textarea
                ref={textarea}
                value={observation}
                maxLength={1000}
                rows={4}
                onChange={(event) => setObservation(event.target.value)}
                placeholder="One small thing you noticed. Avoid precise locations or private details."
                required={outcome === 'completed'}
              />
            </label>
            <p className="small muted">
              Up to 1,000 characters. Optional if you stopped or skipped. Saved
              locally first. AI follow-up is separate and only happens after you
              review selected notes and approve one hosted request. Unsaved
              drafts do not survive a reload—use Save before closing.
            </p>
            <button
              className="primary-button"
              disabled={
                busy || (outcome === 'completed' && !observation.trim())
              }
            >
              Save observation on this device
            </button>
          </fieldset>
        </form>
      </details>
      <div className="journal-sync">
        <h3>Your journal, on your terms.</h3>
        <p className="small muted">
          Local notes are not encrypted or hidden from other people using this
          device. Sync is never automatic.
        </p>
        <div className="journal-actions">
          <button
            className="secondary-button"
            disabled={busy || !connected || !online}
            onClick={() => void journal.check()}
          >
            Check Atlas status
          </button>
          <button
            className="secondary-button"
            disabled={busy || !ready}
            onClick={() => void journal.readCloud()}
          >
            Load cloud journal
          </button>
        </div>
        {journal.status && (
          <p className="small">
            {journal.status.enabled
              ? 'Atlas sync configured; this status does not prove a database connection.'
              : (journalReasons[journal.status.disabled_reason ?? ''] ??
                'Atlas sync is not available.')}
          </p>
        )}
        {!connected && (
          <p className="small muted">
            Connect through Backend connection above to check journal settings.
            Qwen can remain switched off.
          </p>
        )}
        {otherOwners && (
          <p className="small muted">
            Some changes belong to a previously connected journal. They will not
            upload to a different owner.
          </p>
        )}
        <label className="consent">
          <input
            type="checkbox"
            checked={consent}
            disabled={busy || !ready}
            onChange={(event) => {
              setConsent(event.target.checked)
              setApprovedIds(
                event.target.checked
                  ? journal.records
                      .filter(
                        (row) =>
                          (row.kind === 'delete' || row.stage === 'pending') &&
                          (row.owner_id === null ||
                            row.owner_id === journal.status?.owner_id),
                      )
                      .map((row) => row.id)
                  : [],
              )
            }}
          />
          <span>
            For this sync, send eligible saved observations, feedback and
            mission snapshots to MongoDB Atlas, and apply pending deletions.
            Unassigned notes will be linked to this journal. Nothing goes to
            Tinker yet.
          </span>
        </label>
        <button
          className="primary-button"
          disabled={
            busy ||
            !ready ||
            !consent ||
            !journal.records.some(
              (row) =>
                (row.kind === 'delete' || row.stage === 'pending') &&
                (row.owner_id === null ||
                  row.owner_id === journal.status?.owner_id),
            )
          }
          onClick={async () => {
            setConsent(false)
            await journal.sync(approvedIds)
          }}
        >
          {journal.busy ? 'Working on your journal…' : 'Sync pending changes'}
        </button>
      </div>
      <FollowUpPanel
        followUp={followUp}
        entries={followUpEntries}
        owner={journal.status?.enabled ? journal.status.owner_id : null}
        busy={busy}
        connected={connected}
        online={online}
        onAccept={onAccept}
      />
      <div className="journal-entries">
        <h3>Saved observations</h3>
        {journal.restoring ? (
          <p role="status">Opening saved observations…</p>
        ) : (
          !visible.length && (
            <p className="small muted">
              No observations to show yet. No sample journal entries are
              created.
            </p>
          )
        )}
        {visible.map(({ entry, state, local }) => (
          <article className="journal-entry" key={entry.id}>
            <h4>{entry.mission.mission.title}</h4>
            <p className="small muted">
              {entry.outcome} ·{' '}
              {entry.feedback?.replaceAll('_', ' ') ?? 'not rated'} · {state}
            </p>
            <p className="observation-text">
              {entry.observation || 'No observation recorded.'}
            </p>
            <p className="small muted">
              Recorded on device: {new Date(entry.recorded_at).toLocaleString()}
              . Self-reported, not tracked.
            </p>
            {confirming === entry.id ? (
              <div className="delete-confirm">
                <p className="small">
                  Remove this note here? If it may exist in Atlas, deletion will
                  be queued for your next sync. Provider backups may retain
                  data.
                </p>
                <button
                  className="secondary-button"
                  disabled={busy}
                  onClick={async () => {
                    if (local) await journal.remove(entry.id)
                    else await journal.removeCloud(entry.id)
                    setConfirming(null)
                  }}
                >
                  Confirm removal
                </button>
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => setConfirming(null)}
                >
                  Keep note
                </button>
              </div>
            ) : (
              <button
                className="text-button"
                disabled={busy}
                onClick={() => setConfirming(entry.id)}
              >
                Remove observation
              </button>
            )}
          </article>
        ))}
        {journal.records.some((row) => row.kind === 'delete') && (
          <p className="small" role="status">
            Cloud deletion pending. Note content has been removed from this
            device’s outbox; sync to confirm deletion in Atlas.
          </p>
        )}
        {journal.nextAfter && (
          <button
            className="secondary-button"
            disabled={busy || !ready}
            onClick={() => void journal.readCloud(true)}
          >
            Load more cloud observations
          </button>
        )}
      </div>
    </section>
  )
}

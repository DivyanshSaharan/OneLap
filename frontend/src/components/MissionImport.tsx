import { useEffect, useRef, useState } from 'react'
import { settingLabels, type MissionResponse } from '../domain'
import { readMissionFile } from '../missionFile'

interface Props {
  busy: boolean
  hasMission: boolean
  onImport: (response: MissionResponse) => Promise<boolean>
}

export function MissionImport({ busy, hasMission, onImport }: Props) {
  const [preview, setPreview] = useState<MissionResponse | null>(null)
  const [reading, setReading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [reviewed, setReviewed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const lock = useRef(false)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  async function select(file: File) {
    if (busy || lock.current) return
    lock.current = true
    setReading(true)
    setPreview(null)
    setReviewed(false)
    setError(null)
    setSaved(false)
    try {
      const response = await readMissionFile(file)
      if (alive.current) setPreview(response)
    } catch {
      if (alive.current)
        setError(
          'This file could not be opened as a supported mission. Use a single mission-response JSON under 16 KiB. Your current mission was not changed.',
        )
    } finally {
      lock.current = false
      if (alive.current) setReading(false)
    }
  }

  async function accept() {
    if (!preview || !reviewed || busy || lock.current) return
    lock.current = true
    setSaving(true)
    setError(null)
    try {
      if (await onImport(preview)) {
        if (alive.current) {
          setPreview(null)
          setReviewed(false)
          setSaved(true)
        }
      } else if (alive.current) {
        setError('The import was not saved. Your current mission was kept.')
      }
    } catch {
      if (alive.current)
        setError('The import was not saved. Your current mission was kept.')
    } finally {
      lock.current = false
      if (alive.current) setSaving(false)
    }
  }

  const locked = busy || reading || saving
  return (
    <details className="mission-import panel">
      <summary>Use a captured mission · no model request</summary>
      <p className="small muted">
        Choose a single mission-response JSON file. It is read on this device
        only, not uploaded. A full test report is not accepted.
      </p>
      <label className="import-file">
        Mission JSON file
        <input
          type="file"
          accept=".json,application/json"
          disabled={locked}
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) void select(file)
          }}
        />
      </label>
      {reading && <p role="status">Opening the file locally…</p>}
      {error && (
        <p className="import-error" role="alert">
          {error}
        </p>
      )}
      {saved && (
        <p role="status">
          Imported and saved on this device. No model request was made.
        </p>
      )}
      {preview && (
        <section
          className="import-preview"
          aria-labelledby="import-preview-title"
        >
          <span className="eyebrow">FILE PREVIEW · NOT YET SAVED</span>
          <h3 id="import-preview-title">{preview.mission.title}</h3>
          <p>{preview.mission.instruction}</p>
          <p>
            <strong>Remember:</strong> {preview.mission.remember}
          </p>
          <p className="small">
            {preview.mission.minutes} min ·{' '}
            {settingLabels[preview.mission.setting]} ·{' '}
            {preview.mission.conditions} · {preview.mission.focus}
          </p>
          <p className="small">
            The file claims {preview.generation.model} ·{' '}
            {preview.generation.target} · {preview.generation.prompt_version}.
            Model provenance is not verified.
          </p>
          <p className="small">File safety note: {preview.safety_note}</p>
          <p className="small muted">
            Shape and keyword checks are not a safety or grounding assessment.
            Stay in a familiar area you choose; skip or stop if the task or
            conditions do not fit.
          </p>
          <label className="import-consent">
            <input
              type="checkbox"
              checked={reviewed}
              disabled={locked}
              onChange={(event) => setReviewed(event.target.checked)}
            />
            I reviewed this unverified file and want to save its mission on this
            device.
          </label>
          {hasMission && (
            <p className="small">
              Saving replaces the current mission. Existing observation notes
              are kept.
            </p>
          )}
          <div className="journal-actions">
            <button
              type="button"
              className="primary-button"
              disabled={locked || !reviewed}
              onClick={() => void accept()}
            >
              {saving ? 'Saving imported mission…' : 'Save imported mission'}
            </button>
            <button
              type="button"
              className="text-button"
              disabled={locked}
              onClick={() => {
                setPreview(null)
                setReviewed(false)
                setError(null)
              }}
            >
              Discard file preview
            </button>
          </div>
        </section>
      )}
    </details>
  )
}

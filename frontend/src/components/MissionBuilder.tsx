import { useState } from 'react'
import {
  settingLabels,
  type Conditions,
  type Focus,
  type Minutes,
  type MissionRequest,
  type Setting,
} from '../domain'

interface Props {
  disabled: boolean
  busy: boolean
  locked: boolean
  connected: boolean
  online: boolean
  onGenerate: (input: MissionRequest) => Promise<void>
}

export function MissionBuilder({
  disabled,
  busy,
  locked,
  connected,
  online,
  onGenerate,
}: Props) {
  const [input, setInput] = useState<MissionRequest>({
    minutes: 15,
    setting: 'courtyard',
    conditions: 'evening',
    focus: 'general',
  })
  const [consent, setConsent] = useState(false)
  return (
    <section className="builder panel" aria-labelledby="builder-title">
      <span className="eyebrow">01 / BEFORE YOU GO</span>
      <h2 id="builder-title">Make room for a small lap.</h2>
      <p className="muted intro">
        A familiar place. A little time. One thing to notice.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (!disabled && !locked && consent && online) void onGenerate(input)
        }}
      >
        <fieldset disabled={locked} className="choices">
          <legend>How much time feels right?</legend>
          <div className="time-options">
            {([10, 15, 20] as Minutes[]).map((minutes) => (
              <label
                className={`time-choice ${input.minutes === minutes ? 'selected' : ''}`}
                key={minutes}
              >
                <input
                  type="radio"
                  name="minutes"
                  value={minutes}
                  checked={input.minutes === minutes}
                  onChange={() => setInput({ ...input, minutes })}
                />
                <span>
                  {minutes}
                  <small>minutes</small>
                </span>
              </label>
            ))}
          </div>
          <div className="field-grid">
            <label>
              Where will you go?
              <select
                value={input.setting}
                onChange={(event) =>
                  setInput({ ...input, setting: event.target.value as Setting })
                }
              >
                {Object.entries(settingLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              What are the conditions?
              <select
                value={input.conditions}
                onChange={(event) =>
                  setInput({
                    ...input,
                    conditions: event.target.value as Conditions,
                  })
                }
              >
                <option value="evening">Evening</option>
                <option value="daylight">Daylight</option>
              </select>
            </label>
          </div>
          <label className="focus-label">
            What draws your attention?
            <select
              value={input.focus}
              onChange={(event) =>
                setInput({ ...input, focus: event.target.value as Focus })
              }
            >
              <option value="general">Let me discover</option>
              <option value="light">Light & shadows</option>
              <option value="textures">Textures & patterns</option>
              <option value="sounds">Sounds around me</option>
            </select>
          </label>
          <label className="consent">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            <span>
              I understand these selections go to hosted Qwen through Tinker.
            </span>
          </label>
        </fieldset>
        <button
          className="primary-button"
          type="submit"
          disabled={disabled || locked || !consent || !online}
        >
          {busy ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Creating your mission…
            </>
          ) : (
            <>
              Create my small outing <span aria-hidden="true">↗</span>
            </>
          )}
        </button>
        <p className="form-help">
          {!online
            ? 'Generation needs a connection. Your saved mission still works.'
            : !connected
              ? 'Open Private access above to connect before generating.'
              : disabled
                ? 'Generation is not enabled yet. Check the private API settings.'
                : 'One request. One mission. Saved on this device automatically.'}
        </p>
      </form>
    </section>
  )
}

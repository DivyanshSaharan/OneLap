import { useState } from 'react'
import { AccessPanel } from './components/AccessPanel'
import { EmptyMission } from './components/EmptyMission'
import { JournalPanel } from './components/JournalPanel'
import { MissionBuilder } from './components/MissionBuilder'
import { MissionCard } from './components/MissionCard'
import { MissionImport } from './components/MissionImport'
import { Notice } from './components/Notice'
import { PageHeader } from './components/PageHeader'
import { useMission } from './hooks/useMission'
import { useOfflineShell } from './hooks/useOfflineShell'
import { useOnline } from './hooks/useOnline'
import { useJournal } from './journal/useJournal'
import { useFollowUp } from './journal/useFollowUp'

export default function App() {
  const online = useOnline()
  const state = useMission()
  const journal = useJournal(state.accessToken, online, Boolean(state.status))
  const followUp = useFollowUp(state.accessToken, online, Boolean(state.status))
  const shell = useOfflineShell()
  const [pocket, setPocket] = useState(false)
  const [returning, setReturning] = useState(0)
  const busy =
    Boolean(state.busy) ||
    state.restoring ||
    journal.busy ||
    journal.restoring ||
    followUp.busy
  const offlineReady = state.saved && shell.state === 'ready'

  return (
    <div className={`page ${pocket ? 'pocket-page' : ''}`}>
      <PageHeader online={online} />
      <main>
        {!pocket && (
          <section className={`hero ${state.mission ? 'hero-compact' : ''}`}>
            <span className="eyebrow">AFTER WORK, BEFORE SCROLLING</span>
            {state.mission ? (
              <h1>Your small outing.</h1>
            ) : (
              <>
                <h1>
                  A little outside.
                  <br />
                  <em>A little more present.</em>
                </h1>
                <p>
                  Your day has been full. Your next fifteen minutes don’t have
                  to be.
                </p>
                <div className="hero-notes">
                  <span>No location tracking</span>
                  <span>No camera needed</span>
                  <span>Phone away, not phone busy</span>
                </div>
              </>
            )}
          </section>
        )}
        <div className="announcements">
          {!online && (
            <Notice>
              You’re offline. Read your saved mission; connect again when you
              want a new one.
            </Notice>
          )}
          {state.error && <Notice error>{state.error}</Notice>}
          {state.storageError && (
            <Notice error>
              {state.storageError}{' '}
              {!state.mission && (
                <button
                  type="button"
                  className="text-button"
                  disabled={busy}
                  onClick={() => void state.clear()}
                >
                  Clear saved data
                </button>
              )}
            </Notice>
          )}
          {shell.updateAvailable && (
            <Notice>
              An app update is ready.{' '}
              <button
                type="button"
                className="text-button"
                disabled={busy || pocket}
                onClick={shell.update}
              >
                Update when you’re back
              </button>
            </Notice>
          )}
        </div>
        {!pocket && (
          <AccessPanel
            status={state.status}
            busy={busy}
            connecting={state.busy === 'connecting'}
            online={online}
            onConnect={state.connect}
            onDisconnect={state.disconnect}
          />
        )}
        <div className={`mission-layout ${pocket ? 'single' : ''}`}>
          {state.mission && (
            <MissionCard
              response={state.mission}
              imported={state.missionSource === 'imported'}
              saved={state.saved}
              offlineReady={offlineReady}
              busy={busy}
              pocket={pocket}
              focusOnCreate={state.busy === 'generating'}
              onPocket={() => setPocket(true)}
              onClear={() => {
                setPocket(false)
                void state.clear()
              }}
              onSave={() => void state.saveAgain()}
            />
          )}
          {!pocket && (
            <MissionBuilder
              disabled={!state.status?.enabled || state.restoring}
              locked={busy}
              busy={state.busy === 'generating'}
              connected={Boolean(state.status)}
              online={online}
              onGenerate={state.generate}
            />
          )}
          {!state.mission && (
            <EmptyMission
              busy={state.busy === 'generating'}
              restoring={state.restoring}
            />
          )}
        </div>
        {pocket && (
          <div className="pocket-footer">
            <p>Read it once. Put your phone away.</p>
            <p className="small muted">
              No timer, tracking or background model requests. Heading out does
              not mark this mission complete.
            </p>
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setPocket(false)
                setReturning((value) => value + 1)
              }}
            >
              I’m back — record an observation
            </button>
          </div>
        )}
        {!pocket && (
          <MissionImport
            busy={busy}
            hasMission={Boolean(state.mission)}
            onImport={state.importMission}
          />
        )}
        {!pocket && (
          <JournalPanel
            journal={journal}
            followUp={followUp}
            mission={state.mission}
            busy={busy}
            connected={Boolean(state.status)}
            online={online}
            returning={returning}
            onAccept={state.adoptFollowUp}
          />
        )}
        {!pocket && (
          <footer className="page-footer">
            <p>Made for a small break, not another feed.</p>
            <p className="small muted">
              {shell.state === 'ready'
                ? 'Offline app shell cached. Save a mission before disconnecting.'
                : shell.state === 'development'
                  ? 'Development preview · use a production build to test offline reopening.'
                  : shell.state === 'unavailable'
                    ? 'Offline app caching is unavailable. Reopening requires HTTPS or localhost and a compatible browser.'
                    : 'Preparing the offline app shell…'}
            </p>
            <p className="small muted">
              Reflections use selected Atlas notes only after separate sharing
              approval.
            </p>
          </footer>
        )}
      </main>
    </div>
  )
}

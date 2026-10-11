import { useEffect, useState } from 'react'
import { AccessPanel } from './components/AccessPanel'
import { SignInPanel } from './components/SignInPanel'
import { useAuth } from './auth/useAuth'
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
  const auth = useAuth(
    online,
    state.restoring,
    state.connectAccount,
    state.disconnect,
  )
  const shell = useOfflineShell()
  if (!auth.authenticated) {
    return (
      <div className="page">
        <PageHeader online={online} />
        <main>
          <section className="hero">
            <span className="eyebrow">AFTER WORK, BEFORE SCROLLING</span>
            <h1>
              A little outside.
              <br />
              <em>A little more present.</em>
            </h1>
            <p>Sign in to start your small outing. Your journal stays yours.</p>
          </section>
          {!online && (
            <Notice>
              Connect to verify your sign-in before opening OneLap.
            </Notice>
          )}
          <SignInPanel
            auth={auth}
            busy={auth.busy || state.restoring}
            online={online}
            connected={false}
            onConnect={state.connectAccount}
          />
        </main>
      </div>
    )
  }
  return (
    <Workspace
      key={auth.session!.owner_id!}
      state={state}
      auth={auth}
      online={online}
      shell={shell}
    />
  )
}

export function Workspace({
  state,
  auth,
  online,
  shell,
}: {
  state: ReturnType<typeof useMission>
  auth: ReturnType<typeof useAuth>
  online: boolean
  shell: ReturnType<typeof useOfflineShell>
}) {
  const journal = useJournal(
    state.accessToken,
    online,
    Boolean(state.status),
    state.owner,
  )
  const followUp = useFollowUp(
    state.accessToken,
    online,
    Boolean(state.status),
    state.owner,
  )
  const [pocket, setPocket] = useState(false)
  const [returning, setReturning] = useState(0)
  useEffect(() => {
    setPocket(false)
    setReturning(0)
  }, [state.owner])
  const busy =
    Boolean(state.busy) ||
    auth.busy ||
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
        {!pocket && auth.session?.enabled === false && (
          <AccessPanel
            status={state.status}
            busy={busy}
            connecting={state.busy === 'connecting'}
            online={online}
            onConnect={state.connect}
            onDisconnect={state.disconnect}
          />
        )}
        {!pocket && auth.session?.enabled !== false && (
          <SignInPanel
            auth={auth}
            busy={busy}
            online={online}
            connected={Boolean(state.status)}
            onConnect={state.connectAccount}
          />
        )}
        <div className={`mission-layout ${pocket ? 'single' : ''}`}>
          {state.mission && (
            <MissionCard
              response={state.mission}
              imported={state.missionSource === 'imported'}
              followUpOrigin={state.followUpOrigin}
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
              key={`builder:${state.owner ?? 'device'}`}
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
        {!pocket &&
          (state.mission ||
            journal.records.length > 0 ||
            journal.cloud.length > 0 ||
            journal.storageError) && (
            <JournalPanel
              key={`journal:${state.owner ?? 'device'}`}
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
          <MissionImport
            key={`import:${state.owner ?? 'device'}`}
            busy={busy}
            hasMission={Boolean(state.mission)}
            onImport={state.importMission}
          />
        )}
        {!pocket && (
          <footer className="page-footer">
            <p>Made for a small break, not another feed.</p>
            <p className="small muted">
              {shell.state === 'ready'
                ? 'Save a mission before going offline. Reopening needs sign-in verification.'
                : shell.state === 'development'
                  ? 'This preview needs an internet connection to reopen.'
                  : shell.state === 'unavailable'
                    ? 'Offline reopening is unavailable in this browser. Keep this page open.'
                    : 'Preparing for offline reading…'}
            </p>
          </footer>
        )}
      </main>
    </div>
  )
}

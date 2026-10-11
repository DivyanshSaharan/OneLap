import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { mission } from './test/fixtures'

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  journal: vi.fn(),
  followUp: vi.fn(),
  online: true,
}))
vi.mock('./auth/useAuth', () => ({ useAuth: mocks.auth }))
vi.mock('./hooks/useMission', () => ({
  useMission: () => ({
    restoring: false,
    mission,
    owner: '11111111-1111-4111-8111-111111111111',
    connectAccount: vi.fn(),
    disconnect: vi.fn(),
  }),
}))
vi.mock('./hooks/useOnline', () => ({ useOnline: () => mocks.online }))
vi.mock('./hooks/useOfflineShell', () => ({
  useOfflineShell: () => ({
    state: 'ready',
    updateAvailable: false,
    update: vi.fn(),
  }),
}))
vi.mock('./journal/useJournal', () => ({ useJournal: mocks.journal }))
vi.mock('./journal/useFollowUp', () => ({ useFollowUp: mocks.followUp }))

beforeEach(() => {
  vi.clearAllMocks()
  mocks.online = true
  mocks.auth.mockReturnValue({
    session: {
      enabled: true,
      client_id: 'fixture.apps.googleusercontent.com',
      owner_id: null,
      csrf: null,
    },
    authenticated: false,
    busy: false,
    error: null,
    refresh: vi.fn(),
    finish: vi.fn(),
    signOut: vi.fn(),
  })
})

function expectLocked() {
  expect(
    screen.queryByRole('heading', { name: mission.mission.title }),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: /Create my small outing/ }),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByRole('heading', { name: /Bring back one thought/ }),
  ).not.toBeInTheDocument()
  expect(screen.queryByText('Backend connection')).not.toBeInTheDocument()
  expect(screen.queryByText(/Import a mission/)).not.toBeInTheDocument()
  expect(mocks.journal).not.toHaveBeenCalled()
  expect(mocks.followUp).not.toHaveBeenCalled()
}

it('shows only sign-in, never cached missions or journal tools, before login', () => {
  render(<App />)
  expect(
    screen.getByRole('button', { name: 'Sign in with Google' }),
  ).toBeVisible()
  expectLocked()
})

it.each([
  null,
  { enabled: false, client_id: null, owner_id: null, csrf: null },
])(
  'fails closed while identity is unknown or authentication is unavailable: %s',
  (session) => {
    mocks.auth.mockReturnValue({ ...mocks.auth(), session })
    render(<App />)
    expectLocked()
  },
)

it('does not unlock from a saved owner on an offline reload', () => {
  mocks.online = false
  render(<App />)
  expect(screen.getByText(/Connect to verify your sign-in/)).toBeVisible()
  expect(
    screen.getByRole('button', { name: 'Sign in with Google' }),
  ).toBeDisabled()
  expectLocked()
})

it('stays locked when logout is unconfirmed despite retained session metadata', () => {
  mocks.auth.mockReturnValue({
    ...mocks.auth(),
    session: {
      enabled: true,
      client_id: 'fixture.apps.googleusercontent.com',
      owner_id: '11111111-1111-4111-8111-111111111111',
      csrf: 'a'.repeat(43),
    },
    error: 'Sign-out was not confirmed.',
  })
  render(<App />)
  expect(screen.getByText('Your workspace is locked.')).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'Reconnect my journal' }),
  ).not.toBeInTheDocument()
  expectLocked()
})

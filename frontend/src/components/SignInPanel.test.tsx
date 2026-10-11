import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { SignInPanel } from './SignInPanel'
import type { useAuth } from '../auth/useAuth'

const mocks = vi.hoisted(() => ({
  challenge: vi.fn(),
  load: vi.fn(),
  initialize: vi.fn(),
  render: vi.fn(),
}))
vi.mock('../auth/api', () => ({ getChallenge: mocks.challenge }))
vi.mock('../auth/google', () => ({ loadGoogle: mocks.load }))

function auth(owner: string | null = null): ReturnType<typeof useAuth> {
  return {
    session: {
      enabled: true,
      client_id: 'fictional.apps.googleusercontent.com',
      owner_id: owner,
      csrf: owner ? 'a'.repeat(43) : null,
    },
    busy: false,
    authenticated: Boolean(owner),
    error: null,
    refresh: vi.fn(),
    finish: vi.fn().mockResolvedValue(true),
    signOut: vi.fn(),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.challenge.mockResolvedValue({
    nonce: 'n'.repeat(43),
    csrf: 'a'.repeat(43),
  })
  mocks.load.mockResolvedValue({
    initialize: mocks.initialize,
    renderButton: mocks.render,
  })
})

it('loads Google only after clicking and uses a nonce-bound official popup button', async () => {
  const state = auth()
  render(
    <SignInPanel
      auth={state}
      busy={false}
      online
      connected={false}
      onConnect={vi.fn()}
    />,
  )
  expect(mocks.load).not.toHaveBeenCalled()
  await userEvent.click(
    screen.getByRole('button', { name: 'Sign in with Google' }),
  )
  await waitFor(() => expect(mocks.initialize).toHaveBeenCalledOnce())
  const options = mocks.initialize.mock.calls[0][0]
  expect(options).toMatchObject({
    nonce: 'n'.repeat(43),
    ux_mode: 'popup',
    auto_select: false,
  })
  options.callback({ credential: 'fictional-token' })
  expect(state.finish).toHaveBeenCalledWith('fictional-token', 'a'.repeat(43))
  options.callback({ credential: 'fictional-token' })
  expect(state.finish).toHaveBeenCalledOnce()
})

it('does not allow login or logout while offline', () => {
  const { rerender } = render(
    <SignInPanel
      auth={auth()}
      busy={false}
      online={false}
      connected={false}
      onConnect={vi.fn()}
    />,
  )
  expect(
    screen.getByRole('button', { name: 'Sign in with Google' }),
  ).toBeDisabled()
  rerender(
    <SignInPanel
      auth={auth('11111111-1111-4111-8111-111111111111')}
      busy={false}
      online={false}
      connected
      onConnect={vi.fn()}
    />,
  )
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeDisabled()
})

it('does not expose a legacy token input when auth availability is unknown', () => {
  const state = { ...auth(), session: null }
  render(
    <SignInPanel
      auth={state}
      busy={false}
      online
      connected={false}
      onConnect={vi.fn()}
    />,
  )
  expect(screen.queryByLabelText('Server access token')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Check sign-in' })).toBeEnabled()
})

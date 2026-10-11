import { StrictMode, type ReactNode } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '../api'
import { useAuth } from './useAuth'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}))
vi.mock('./api', () => ({
  getSession: mocks.get,
  login: mocks.login,
  logout: mocks.logout,
}))

const signedOut = {
  enabled: true,
  client_id: 'fictional.apps.googleusercontent.com',
  owner_id: null,
  csrf: null,
}
const session = {
  ...signedOut,
  owner_id: '11111111-1111-4111-8111-111111111111',
  csrf: 'a'.repeat(43),
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue(signedOut)
  mocks.login.mockResolvedValue(session)
  mocks.logout.mockResolvedValue(undefined)
})

function setup(online = true, restoring = false, strict = false) {
  const connect = vi.fn().mockResolvedValue(true)
  const disconnect = vi.fn().mockResolvedValue(undefined)
  const hook = renderHook(
    () => useAuth(online, restoring, connect, disconnect),
    strict
      ? {
          wrapper: ({ children }: { children: ReactNode }) => (
            <StrictMode>{children}</StrictMode>
          ),
        }
      : {},
  )
  return { ...hook, connect, disconnect }
}

it('checks identity only, without cloud notes or model calls', async () => {
  const { result, connect } = setup()
  await waitFor(() => expect(result.current.session).toEqual(signedOut))
  expect(connect).not.toHaveBeenCalled()
  expect(mocks.login).not.toHaveBeenCalled()
  expect(result.current.authenticated).toBe(false)
})

it('restores a valid account and connects its journal slot', async () => {
  mocks.get.mockResolvedValue(session)
  const { result, connect } = setup()
  await waitFor(() => expect(result.current.busy).toBe(false))
  expect(result.current.session).toEqual(session)
  expect(connect).toHaveBeenCalledWith(session.owner_id)
  expect(result.current.authenticated).toBe(true)
})

it('does not contact Google or Atlas while offline or restoring device data', () => {
  setup(false)
  setup(true, true)
  expect(mocks.get).not.toHaveBeenCalled()
})

it('does not fall back to local access when identity checking fails', async () => {
  mocks.get.mockRejectedValue(new ApiError('network_unavailable'))
  const { result, connect } = setup()
  await waitFor(() => expect(result.current.error).not.toBeNull())
  expect(result.current.session).toBeNull()
  expect(result.current.authenticated).toBe(false)
  expect(connect).not.toHaveBeenCalled()
})

it('signs in once, clears the old account and connects the verified owner', async () => {
  const { result, connect, disconnect } = setup()
  await waitFor(() => expect(result.current.session).toEqual(signedOut))
  disconnect.mockClear()
  await act(async () => {
    await result.current.finish('fictional-token', 'n'.repeat(43))
  })
  expect(mocks.login).toHaveBeenCalledOnce()
  expect(disconnect).toHaveBeenCalledOnce()
  expect(connect).toHaveBeenCalledWith(session.owner_id)
  expect(result.current.session).toEqual(session)
})

it('revokes on sign-out and clears the account locally without deleting its saved notes', async () => {
  mocks.get.mockResolvedValue(session)
  const { result, disconnect } = setup()
  await waitFor(() => expect(result.current.session).toEqual(session))
  disconnect.mockClear()
  await act(async () => {
    await result.current.signOut()
  })
  expect(disconnect).toHaveBeenCalledOnce()
  expect(mocks.logout).toHaveBeenCalledOnce()
  expect(result.current.session?.owner_id).toBeNull()
  expect(result.current.authenticated).toBe(false)
})

it('does not falsely report successful sign-out when revocation fails', async () => {
  mocks.get.mockResolvedValue(session)
  mocks.logout.mockRejectedValue(new ApiError('network_unavailable'))
  const { result, disconnect } = setup()
  await waitFor(() => expect(result.current.session).toEqual(session))
  disconnect.mockClear()
  await act(async () => {
    await result.current.signOut()
  })
  expect(disconnect).toHaveBeenCalledOnce()
  expect(result.current.error).toContain('Sign-out was not confirmed')
  expect(result.current.session).toEqual(session)
  expect(result.current.authenticated).toBe(false)
})

it('never grants workspace access when Google authentication is disabled', async () => {
  mocks.get.mockResolvedValue({
    enabled: false,
    client_id: null,
    owner_id: null,
    csrf: null,
  })
  const { result } = setup()
  await waitFor(() => expect(result.current.session?.enabled).toBe(false))
  expect(result.current.authenticated).toBe(false)
})

it('locks immediately while sign-out is still pending', async () => {
  mocks.get.mockResolvedValue(session)
  let complete!: () => void
  mocks.logout.mockReturnValue(
    new Promise<void>((resolve) => {
      complete = resolve
    }),
  )
  const { result } = setup()
  await waitFor(() => expect(result.current.authenticated).toBe(true))
  let pending!: Promise<void>
  act(() => {
    pending = result.current.signOut()
  })
  await waitFor(() => expect(mocks.logout).toHaveBeenCalledOnce())
  expect(result.current.authenticated).toBe(false)
  await act(async () => {
    complete()
    await pending
  })
})

it('locks an offline account when its session is invalidated', async () => {
  mocks.get.mockResolvedValue(session)
  const connect = vi.fn().mockResolvedValue(true)
  const disconnect = vi.fn().mockResolvedValue(undefined)
  const { result, rerender } = renderHook(
    ({ online }) => useAuth(online, false, connect, disconnect),
    { initialProps: { online: true } },
  )
  await waitFor(() => expect(result.current.authenticated).toBe(true))
  rerender({ online: false })
  act(() => {
    window.dispatchEvent(new Event('onelap:session-expired'))
  })
  expect(result.current.authenticated).toBe(false)
  expect(result.current.session).toBeNull()
  expect(mocks.get).toHaveBeenCalledOnce()
})

it('clears stale account access and refreshes after an expired-session event', async () => {
  mocks.get.mockResolvedValueOnce(session).mockResolvedValue(signedOut)
  const { result, disconnect } = setup()
  await waitFor(() => expect(result.current.session).toEqual(session))
  disconnect.mockClear()
  act(() => {
    window.dispatchEvent(new Event('onelap:session-expired'))
  })
  await waitFor(() => expect(result.current.session).toEqual(signedOut))
  expect(disconnect).toHaveBeenCalledOnce()
})

it('finishes checking under StrictMode without leaving the UI stuck', async () => {
  const { result } = setup(true, false, true)
  await waitFor(() => expect(result.current.session).toEqual(signedOut))
  expect(result.current.busy).toBe(false)
})

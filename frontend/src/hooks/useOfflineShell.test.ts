import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useOfflineShell } from './useOfflineShell'

let service: EventTarget & {
  register: ReturnType<typeof vi.fn>
  ready: Promise<unknown>
}
const originalServiceWorker = Object.getOwnPropertyDescriptor(
  navigator,
  'serviceWorker',
)
beforeEach(() => {
  vi.stubEnv('PROD', true)
  vi.stubGlobal('isSecureContext', true)
  service = Object.assign(new EventTarget(), {
    register: vi.fn(),
    ready: Promise.resolve({}),
  })
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: service,
  })
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllEnvs()
  if (originalServiceWorker)
    Object.defineProperty(navigator, 'serviceWorker', originalServiceWorker)
  else Reflect.deleteProperty(navigator, 'serviceWorker')
})

function registration(active = true) {
  const worker = Object.assign(new EventTarget(), {
    state: 'installing',
    postMessage: vi.fn(),
  })
  return Object.assign(new EventTarget(), {
    active: active ? {} : null,
    waiting: worker,
    installing: worker,
  })
}

it('does not register a service worker during development', () => {
  vi.stubEnv('PROD', false)
  const { result } = renderHook(useOfflineShell)
  expect(result.current.state).toBe('development')
  expect(service.register).not.toHaveBeenCalled()
})
it('reports an insecure context without trying to cache the app', () => {
  vi.stubGlobal('isSecureContext', false)
  const { result } = renderHook(useOfflineShell)
  expect(result.current.state).toBe('unavailable')
  expect(service.register).not.toHaveBeenCalled()
})
it('reports registration failure without perpetual loading', async () => {
  service.register.mockRejectedValue(new Error('installation failed'))
  const { result } = renderHook(useOfflineShell)
  await waitFor(() => expect(result.current.state).toBe('unavailable'))
})
it('times out an installation which never becomes ready', async () => {
  vi.useFakeTimers()
  service.ready = new Promise(() => {})
  service.register.mockResolvedValue(registration(false))
  const { result } = renderHook(useOfflineShell)
  await act(async () => {
    await vi.advanceTimersByTimeAsync(20000)
  })
  expect(result.current.state).toBe('unavailable')
})
it('does not mistake first installation for an app update', async () => {
  const value = registration(false)
  service.register.mockResolvedValue(value)
  const { result } = renderHook(useOfflineShell)
  await waitFor(() => expect(result.current.state).toBe('ready'))
  await act(async () => {
    value.installing.state = 'installed'
    value.installing.dispatchEvent(new Event('statechange'))
  })
  expect(result.current.updateAvailable).toBe(false)
})
it('only activates a waiting update after an explicit user action', async () => {
  const value = registration()
  service.register.mockResolvedValue(value)
  const { result, unmount } = renderHook(useOfflineShell)
  await waitFor(() => expect(result.current.updateAvailable).toBe(true))
  expect(value.waiting.postMessage).not.toHaveBeenCalled()
  act(() => result.current.update())
  expect(value.waiting.postMessage).toHaveBeenCalledExactlyOnceWith(
    'SKIP_WAITING',
  )
  const removed = vi.spyOn(value, 'removeEventListener')
  const workerRemoved = vi.spyOn(value.installing, 'removeEventListener')
  unmount()
  expect(removed).toHaveBeenCalledWith('updatefound', expect.any(Function))
  expect(workerRemoved).toHaveBeenCalledWith(
    'statechange',
    expect.any(Function),
  )
})

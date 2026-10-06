import { expect, it, vi } from 'vitest'
import { workerSource } from './worker'

function worker() {
  const handlers: Record<string, (event: any) => void> = {}
  const cache = {
    addAll: vi.fn().mockResolvedValue(undefined),
    match: vi.fn().mockResolvedValue('cached-shell'),
  }
  const caches = {
    open: vi.fn().mockResolvedValue(cache),
    keys: vi
      .fn()
      .mockResolvedValue([
        'onelap-shell-old',
        'other-app-cache',
        'onelap-shell-test',
      ]),
    delete: vi.fn().mockResolvedValue(true),
  }
  const self = {
    registration: { scope: 'http://localhost/' },
    location: { origin: 'http://localhost' },
    clients: { claim: vi.fn().mockResolvedValue(undefined) },
    skipWaiting: vi.fn(),
    addEventListener: (name: string, handler: (event: any) => void) => {
      handlers[name] = handler
    },
  }
  new Function(
    'self',
    'caches',
    workerSource(['index.html', 'assets/app.js'], 'onelap-shell-test'),
  )(self, caches)
  return { handlers, cache, caches, self }
}

it('precaches only the explicit generic shell assets', async () => {
  const { handlers, cache } = worker()
  let task!: Promise<void>
  handlers.install({
    waitUntil: (value: Promise<void>) => {
      task = value
    },
  })
  await task
  expect(cache.addAll).toHaveBeenCalledWith([
    'http://localhost/index.html',
    'http://localhost/assets/app.js',
  ])
})
it.each([
  ['http://localhost/api/missions', 'POST', 'cors'],
  ['http://localhost/api/model/status', 'GET', 'cors'],
  ['http://localhost/health', 'GET', 'cors'],
  ['http://external.example/assets/app.js', 'GET', 'cors'],
  ['http://localhost/private.json', 'GET', 'cors'],
])(
  'does not intercept private or unrelated requests %s',
  (url, method, mode) => {
    const { handlers } = worker()
    const respondWith = vi.fn()
    handlers.fetch({ request: { url, method, mode }, respondWith })
    expect(respondWith).not.toHaveBeenCalled()
  },
)
it('serves offline navigations from the cached generic shell', async () => {
  const { handlers, cache } = worker()
  let task!: Promise<unknown>
  handlers.fetch({
    request: { url: 'http://localhost/', method: 'GET', mode: 'navigate' },
    respondWith: (value: Promise<unknown>) => {
      task = value
    },
  })
  expect(await task).toBe('cached-shell')
  expect(cache.match).toHaveBeenCalledWith('http://localhost/index.html')
})
it('removes only obsolete OneLap shell caches', async () => {
  const { handlers, caches, self } = worker()
  let task!: Promise<void>
  handlers.activate({
    waitUntil: (value: Promise<void>) => {
      task = value
    },
  })
  await task
  expect(caches.delete).toHaveBeenCalledExactlyOnceWith('onelap-shell-old')
  expect(self.clients.claim).toHaveBeenCalledTimes(1)
})
it('matches public bundle assets despite a preview-server Vary header', async () => {
  const { handlers, cache } = worker()
  const request = {
    url: 'http://localhost/assets/app.js',
    method: 'GET',
    mode: 'cors',
  }
  let task!: Promise<unknown>
  handlers.fetch({
    request,
    respondWith: (value: Promise<unknown>) => {
      task = value
    },
  })
  expect(await task).toBe('cached-shell')
  expect(cache.match).toHaveBeenCalledWith(request, { ignoreVary: true })
})
it('activates an update only upon the explicit message', () => {
  const { handlers, self } = worker()
  handlers.message({ data: 'other' })
  expect(self.skipWaiting).not.toHaveBeenCalled()
  handlers.message({ data: 'SKIP_WAITING' })
  expect(self.skipWaiting).toHaveBeenCalledTimes(1)
})

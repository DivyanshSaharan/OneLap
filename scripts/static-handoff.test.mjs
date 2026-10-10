import assert from 'node:assert/strict'
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { request } from 'node:http'
import { join, relative } from 'node:path'
import { after, before, test } from 'node:test'
import {
  loadPublicFiles,
  projectRoot,
  startHandoff,
} from './static-handoff.mjs'

let temporary
let preview
let loaded
const fixturesRoot = join(projectRoot, '.data/handoff-tests')
const sentinel = 'private-test-sentinel-never-served'
before(async () => {
  await mkdir(fixturesRoot, { recursive: true })
  temporary = await mkdtemp(join(fixturesRoot, 'run-'))
  const dist = join(temporary, 'dist')
  await mkdir(join(dist, 'assets'), { recursive: true })
  for (const name of [
    'index.html',
    'sw.js',
    'icon.svg',
    'manifest.webmanifest',
  ])
    await writeFile(join(dist, name), 'public fixture')
  await writeFile(join(dist, 'assets/app.js'), 'public javascript fixture')
  await writeFile(join(dist, 'assets/app.css'), 'public css fixture')
  await writeFile(join(dist, 'assets/app.js.map'), sentinel)
  await writeFile(join(dist, '.env'), sentinel)
  await writeFile(join(dist, 'private.json'), sentinel)
  const capture = join(temporary, 'capture.json')
  await writeFile(capture, '{"synthetic_fixture":true}')
  loaded = await loadPublicFiles({ dist, capture })
  preview = await startHandoff({ port: 0, publicFiles: loaded })
})
after(async () => {
  await preview?.close()
  if (temporary) {
    const scoped = relative(fixturesRoot, temporary)
    assert.match(scoped, /^run-[\w-]+$/)
    await rm(temporary, { recursive: true })
  }
})

function read(path, { method = 'GET', host } = {}) {
  const address = new URL(preview.origin)
  return new Promise((accept, reject) => {
    const req = request(
      {
        hostname: address.hostname,
        port: address.port,
        path,
        method,
        ...(host ? { headers: { Host: host } } : {}),
      },
      (response) => {
        const chunks = []
        response.on('data', (chunk) => chunks.push(chunk))
        response.on('end', () =>
          accept({
            status: response.statusCode,
            headers: response.headers,
            body: Buffer.concat(chunks).toString('utf8'),
          }),
        )
      },
    )
    req.on('error', reject)
    req.end()
  })
}

test('loads only explicit public files, never project secrets or source maps', () => {
  assert.deepEqual([...loaded.files.keys()].sort(), [
    '/assets/app.css',
    '/assets/app.js',
    '/captured-mission.json',
    '/handoff',
    '/handoff.css',
    '/icon.svg',
    '/index.html',
    '/manifest.webmanifest',
    '/sw.js',
  ])
  assert.match(loaded.publicFilesSha256, /^[a-f0-9]{64}$/)
  assert.ok(
    [...loaded.files.values()].every(({ body }) => !body.includes(sentinel)),
  )
})
test('serves the built app with no-store and browser boundary headers', async () => {
  const result = await read('/')
  assert.equal(result.status, 200)
  assert.equal(result.body, 'public fixture')
  assert.equal(result.headers['cache-control'], 'no-store')
  assert.equal(result.headers['x-content-type-options'], 'nosniff')
  assert.equal(result.headers['referrer-policy'], 'no-referrer')
  assert.match(
    result.headers['content-security-policy'],
    /frame-ancestors 'none'/,
  )
  assert.equal(result.headers['access-control-allow-origin'], undefined)
})
test('supplies only the public capture as an explicit file download', async () => {
  const result = await read('/captured-mission.json')
  assert.equal(result.status, 200)
  assert.deepEqual(JSON.parse(result.body), { synthetic_fixture: true })
  assert.match(result.headers['content-disposition'], /attachment/)
})
test('the handoff labels the base capture, limitations and absence of a backend', async () => {
  const result = await read('/handoff')
  assert.equal(result.status, 200)
  assert.match(result.body, /no backend or API proxy/)
  assert.match(result.body, /base Qwen synthetic-test capture/)
  assert.match(result.body, /No actual phone or outdoor test is claimed/)
})
test('HEAD returns the same headers without body', async () => {
  const result = await read('/assets/app.js', { method: 'HEAD' })
  assert.equal(result.status, 200)
  assert.equal(result.body, '')
  assert.equal(result.headers['content-length'], '25')
})
test('accepts the phone localhost host for the same mapped port', async () => {
  const result = await read('/', {
    host: `localhost:${new URL(preview.origin).port}`,
  })
  assert.equal(result.status, 200)
})
test('rejects non-local Host metadata', async () => {
  const result = await read('/', { host: 'untrusted.example' })
  assert.equal(result.status, 421)
})
for (const method of ['POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
  test(`rejects ${method} without forwarding or accepting uploads`, async () => {
    const result = await read('/api/missions', { method })
    assert.equal(result.status, 405)
    assert.equal(result.body, '')
    assert.equal(result.headers.allow, 'GET, HEAD')
  })
for (const path of [
  '/.env',
  '/private.json',
  '/assets/app.js.map',
  '/assets/',
  '/../.env',
  '/%2e%2e/.env',
  '/assets/%2e%2e/.env',
  '/api/model/status',
  '/api/journal/status',
])
  test(`never serves or proxies ${path}`, async () => {
    const result = await read(path)
    assert.equal(result.status, 404)
    assert.equal(result.body, '')
  })
test('does not fall back to the app shell for arbitrary private-looking routes', async () => {
  assert.equal((await read('/unknown')).status, 404)
  assert.equal((await read('/index.html?cache-test=1')).status, 200)
})
test('refuses missing builds before opening a listener', async () => {
  await assert.rejects(loadPublicFiles({ dist: join(temporary, 'missing') }))
})
test('refuses oversized captures', async () => {
  const capture = join(temporary, 'oversized.json')
  await writeFile(capture, ' '.repeat(16 * 1024 + 1))
  await assert.rejects(
    loadPublicFiles({ dist: join(temporary, 'dist'), capture }),
    /unsupported_public_file/,
  )
})

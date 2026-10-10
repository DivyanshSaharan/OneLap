import { createHash } from 'node:crypto'
import { lstat, readFile, readdir } from 'node:fs/promises'
import { createServer } from 'node:http'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const projectRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '..',
)
export const capturePath = join(
  projectRoot,
  'examples/captured-followup-2026-10-10.json',
)

const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.webmanifest': 'application/manifest+json',
  '.json': 'application/json; charset=utf-8',
}
const handoff = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OneLap · private phone handoff</title>
<link rel="stylesheet" href="/handoff.css"></head><body><main>
<p class="eyebrow">ONELAP / NO-SPEND FIELD CHECK</p>
<h1>Read once. Then step outside.</h1>
<p>This static preview has <strong>no backend or API proxy</strong>.
It cannot generate missions, sync to Atlas or request a reflection.</p>
<ol>
<li><a href="/captured-mission.json" download="captured-mission.json">Download the captured mission JSON</a> while connected.</li>
<li><a href="/">Open OneLap</a>, expand <strong>Use a captured mission · no model request</strong>, choose the downloaded file and review it.</li>
<li>Save only if it suits you. Wait for <strong>Saved on this device · ready to reopen offline</strong>.</li>
<li>Unplug USB, turn off networking, reload <strong>the app at /</strong> and check the mission remains.</li>
<li>Choose <strong>I’m heading out</strong>, pocket the phone and record a note when back. Stop or skip if unsuitable.</li>
</ol>
<p>The file is an earlier <strong>base Qwen synthetic-test capture</strong>, not a fresh personalized request.
It assumes night and objects that were not supplied. Review those weaknesses; this is not a safety assessment.</p>
<p>No actual phone or outdoor test is claimed by this page. Notes stay in this browser until you explicitly share them elsewhere.
The handoff page and download are not cached for offline use; the app shell and saved mission are.</p>
<p>After testing, remove only this USB port mapping and disable USB debugging if no longer needed.
No public tunnel, precise location, GPS or camera is required.</p>
</main></body></html>`
const handoffStyle = `:root{font-family:system-ui,sans-serif;background:#f6f5ee;color:#25382e}
main{max-width:620px;margin:40px auto;padding:0 22px;line-height:1.7}
h1{font-family:Georgia,serif;font-size:38px;line-height:1.2}
a{color:#244b3c;text-underline-offset:4px}li{margin:18px 0}
.eyebrow{font-size:12px;letter-spacing:1.5px}ol{padding-left:24px}`

async function publicFile(path, limit = 4 * 1024 * 1024) {
  const info = await lstat(path)
  if (!info.isFile() || info.isSymbolicLink() || info.size > limit)
    throw new Error('unsupported_public_file')
  return readFile(path)
}

export async function loadPublicFiles({
  dist = join(projectRoot, 'dist'),
  capture = capturePath,
} = {}) {
  const files = new Map()
  const distInfo = await lstat(dist)
  if (!distInfo.isDirectory() || distInfo.isSymbolicLink())
    throw new Error('unsupported_build_directory')
  for (const name of [
    'index.html',
    'sw.js',
    'icon.svg',
    'manifest.webmanifest',
  ]) {
    const extension = name.slice(name.lastIndexOf('.'))
    files.set(`/${name}`, {
      body: await publicFile(join(dist, name)),
      type: types[extension],
    })
  }
  const assets = join(dist, 'assets')
  const assetInfo = await lstat(assets)
  if (!assetInfo.isDirectory() || assetInfo.isSymbolicLink())
    throw new Error('unsupported_asset_directory')
  for (const file of await readdir(assets, { withFileTypes: true })) {
    if (!file.isFile() || !/^[\w.-]+\.(?:js|css)$/.test(file.name)) continue
    const extension = file.name.slice(file.name.lastIndexOf('.'))
    files.set(`/assets/${file.name}`, {
      body: await publicFile(join(assets, file.name)),
      type: types[extension],
    })
  }
  const example = await publicFile(capture, 16 * 1024)
  JSON.parse(example.toString('utf8'))
  files.set('/captured-mission.json', {
    body: example,
    type: types['.json'],
    download: true,
  })
  files.set('/handoff', { body: Buffer.from(handoff), type: types['.html'] })
  files.set('/handoff.css', {
    body: Buffer.from(handoffStyle),
    type: types['.css'],
  })
  const hash = createHash('sha256')
  for (const [path, { body }] of [...files].sort(([a], [b]) =>
    a.localeCompare(b),
  ))
    hash.update(path).update(body)
  return { files, publicFilesSha256: hash.digest('hex') }
}

export async function startHandoff({ port = 4176, publicFiles } = {}) {
  const loaded = publicFiles ?? (await loadPublicFiles())
  const apiAttempts = []
  const server = createServer((request, response) => {
    const host = request.headers.host
    const activePort = server.address().port
    response.setHeader('Cache-Control', 'no-store')
    response.setHeader('X-Content-Type-Options', 'nosniff')
    response.setHeader('Referrer-Policy', 'no-referrer')
    response.setHeader('Cross-Origin-Resource-Policy', 'same-origin')
    response.setHeader(
      'Content-Security-Policy',
      "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    )
    if (
      ![`localhost:${activePort}`, `127.0.0.1:${activePort}`].includes(host)
    ) {
      response.writeHead(421).end()
      return
    }
    const path = (request.url ?? '').split('?')[0]
    if (path.startsWith('/api/') || path === '/api') apiAttempts.push(path)
    if (!['GET', 'HEAD'].includes(request.method)) {
      response.setHeader('Allow', 'GET, HEAD')
      response.writeHead(405).end()
      return
    }
    // Exact, preloaded public routes only; never interpret filesystem paths.
    const file = loaded.files.get(path === '/' ? '/index.html' : path)
    if (!file) {
      response.writeHead(404).end()
      return
    }
    response.setHeader('Content-Type', file.type)
    response.setHeader('Content-Length', file.body.byteLength)
    if (file.download)
      response.setHeader(
        'Content-Disposition',
        'attachment; filename="captured-mission.json"',
      )
    response.writeHead(200)
    response.end(request.method === 'HEAD' ? undefined : file.body)
  })
  server.requestTimeout = 10000
  server.headersTimeout = 10000
  server.on('clientError', (_error, socket) => socket.destroy())
  await new Promise((accept, reject) => {
    server.once('error', reject)
    server.listen(port, '127.0.0.1', accept)
  })
  return {
    origin: `http://127.0.0.1:${server.address().port}`,
    publicFilesSha256: loaded.publicFilesSha256,
    apiAttempts,
    close: () =>
      new Promise((accept, reject) => {
        server.close((error) => (error ? reject(error) : accept()))
        server.closeAllConnections()
      }),
  }
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  if (process.argv.length !== 2) {
    process.stderr.write(
      'No arguments supported. Use the fixed loopback preview.\n',
    )
    process.exitCode = 1
  } else {
    try {
      const preview = await startHandoff()
      process.stdout.write(
        `${preview.origin}/handoff\nStatic files only; no backend, credentials, model calls or cloud sync.\nCtrl+C stops this preview.\n`,
      )
      for (const signal of ['SIGINT', 'SIGTERM'])
        process.once(signal, async () => {
          await preview.close()
        })
    } catch {
      process.stderr.write(
        'Preview could not start. Build first and check that port 4176 is free.\n',
      )
      process.exitCode = 1
    }
  }
}

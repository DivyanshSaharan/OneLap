import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { promisify } from 'node:util'

const execute = promisify(execFile)
const image = process.argv[2] ?? 'onelap:local'
if (process.argv.length > 3 || !/^[a-z0-9][a-z0-9:./_-]*$/.test(image))
  throw new Error('Expected one local Docker image name')

const name = `onelap-smoke-${randomUUID()}`
let container
async function docker(...args) {
  return (
    await execute('docker', args, { timeout: 30_000, maxBuffer: 128_000 })
  ).stdout.trim()
}

const checks = `
import json, os, re, urllib.request, urllib.error
from pathlib import Path
assert os.getuid() != 0
assert not Path('/app/.env').exists()
assert not Path('/app/.data/experiments').exists()
assert Path('/app/datasets/onelap-sft-v1.manifest.json').is_file()
def get(path, headers=None):
    request = urllib.request.Request('http://127.0.0.1:10000' + path,
        headers={'Host': 'localhost:4178', **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, response.headers, response.read().decode()
    except urllib.error.HTTPError as response:
        return response.code, response.headers, response.read().decode()
status, headers, html = get('/')
assert status == 200 and 'text/html' in headers['Content-Type']
for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html):
    status, headers, body = get(asset)
    assert status == 200
    assert ('javascript' if asset.endswith('.js') else 'text/css') in headers['Content-Type']
    assert 'Use a captured mission' not in body and 'Mission JSON file' not in body
status, headers, body = get('/sw.js')
assert status == 200 and 'javascript' in headers['Content-Type']
assert get('/health')[0] == 200
status, headers, body = get('/api/auth/session')
assert status == 200 and 'no-store' in headers['Cache-Control']
identity = json.loads(body)
assert identity['enabled'] is True and identity['owner_id'] is None
assert get('/api/model/status')[0] == 401
assert get('/api/model/status', {'Authorization': 'Bearer fictional-test-only'})[0] == 401
assert get('/api/journal/status')[0] == 401
assert get('/api/auth/session', {'Host': 'attacker.invalid'})[0] == 403
assert get('/api/auth/session', {'Origin': 'https://attacker.invalid'})[0] == 403
print(json.dumps({'status': 'passed', 'non_root': True, 'static_assets': True,
    'anonymous_access_rejected': True, 'private_files_excluded': True,
    'mission_importer_absent': True, 'remote_network': 'disabled'}))
`

try {
  container = await docker(
    'run',
    '--detach',
    '--name',
    name,
    '--network',
    'none',
    '--cap-drop',
    'ALL',
    '--security-opt',
    'no-new-privileges:true',
    '-e',
    'GOOGLE_CLIENT_ID=fictional.apps.googleusercontent.com',
    '-e',
    'GOOGLE_CLIENT_SECRET=fictional-container-test-key-not-a-real-secret',
    '-e',
    'ONELAP_AUTH_ORIGINS=http://localhost:4178',
    image,
  )
  assert.match(container, /^[a-f0-9]{64}$/)
  let ready = false
  for (let attempt = 0; attempt < 30; attempt++) {
    try {
      await docker(
        'exec',
        container,
        'python',
        '-c',
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:10000/health', timeout=1)",
      )
      ready = true
      break
    } catch {
      if (
        (await docker(
          'inspect',
          '--format',
          '{{.State.Running}}',
          container,
        )) !== 'true'
      )
        throw new Error('Smoke container exited before becoming ready')
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
  }
  assert.ok(ready, 'Container did not become ready within 30 checks')
  console.log(await docker('exec', container, 'python', '-c', checks))
  const healthcheck = await docker(
    'inspect',
    '--format',
    '{{json .Config.Healthcheck.Test}}',
    container,
  )
  assert.ok(healthcheck.includes('/health'))
} finally {
  if (container) {
    await docker('stop', '--time', '5', container)
    await docker('rm', container)
    console.log('Disposable smoke container removed; image retained.')
  }
}

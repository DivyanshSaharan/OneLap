import assert from 'node:assert/strict'
import { test } from 'node:test'
import { RequestBoundary } from './browser-workflow.mjs'

const input = {
  origin: 'http://127.0.0.1:8770',
  token: 'fictional-token',
  owner: '11111111-1111-4111-8111-111111111111',
  request: {
    minutes: 15,
    setting: 'courtyard',
    conditions: 'daylight',
    focus: 'textures',
  },
  observation: 'Fictional observation — not a real outing.',
}
const headers = {
  authorization: `Bearer ${input.token}`,
  'x-onelap-journal-owner': input.owner,
}
const entry = {
  id: '22222222-2222-4222-8222-222222222222',
  observation: input.observation,
  outcome: 'completed',
  feedback: 'too_difficult',
}
function admit(boundary, path, method = 'GET', body = null, options = headers) {
  boundary.admit(input.origin + path, method, options, body)
}

test('permits exactly one mission, synthetic upload, selected follow-up and scoped deletion', () => {
  const boundary = new RequestBoundary(input)
  admit(boundary, '/assets/index-a1b2.js')
  admit(boundary, '/api/model/status')
  admit(boundary, '/api/missions', 'POST', input.request)
  admit(boundary, '/api/journal/entries', 'POST', {
    owner_id: input.owner,
    entry,
  })
  admit(boundary, '/api/followups', 'POST', {
    source_id: entry.id,
    context_ids: [],
  })
  admit(boundary, `/api/journal/entries/${entry.id}`, 'DELETE')
  assert.equal(boundary.modelAttempts, 2)
  assert.throws(() => admit(boundary, '/api/missions', 'POST', input.request))
  assert.throws(() =>
    admit(boundary, '/api/followups', 'POST', {
      source_id: entry.id,
      context_ids: [],
    }),
  )
})

for (const path of [
  '/.env',
  '/api/unknown',
  '/api/journal/entries?after=personal',
  '/assets/source.js.map',
  '/handoff',
]) {
  test(`rejects unexpected path ${path}`, () => {
    assert.throws(() => admit(new RequestBoundary(input), path))
  })
}

test('rejects external origins and missing or wrong access tokens', () => {
  const boundary = new RequestBoundary(input)
  assert.throws(() => boundary.admit('https://example.com/', 'GET', {}, null))
  assert.throws(() => admit(boundary, '/api/model/status', 'GET', null, {}))
  assert.throws(() =>
    admit(boundary, '/api/model/status', 'GET', null, {
      authorization: 'wrong',
    }),
  )
})

test('rejects changed mission selections and private notes', () => {
  assert.throws(() =>
    admit(new RequestBoundary(input), '/api/missions', 'POST', {
      ...input.request,
      minutes: 20,
    }),
  )
  assert.throws(() =>
    admit(new RequestBoundary(input), '/api/journal/entries', 'POST', {
      owner_id: input.owner,
      entry: { ...entry, observation: 'PRIVATE NOTE' },
    }),
  )
})

test('rejects other owners, extra context and deletion of unrelated entries', () => {
  const boundary = new RequestBoundary(input)
  admit(boundary, '/api/journal/entries', 'POST', {
    owner_id: input.owner,
    entry,
  })
  assert.throws(() =>
    admit(boundary, '/api/journal/entries', 'GET', null, {
      ...headers,
      'x-onelap-journal-owner': 'other',
    }),
  )
  assert.throws(() =>
    admit(boundary, '/api/followups', 'POST', {
      source_id: entry.id,
      context_ids: ['other'],
    }),
  )
  assert.throws(() => admit(boundary, '/api/journal/entries/other', 'DELETE'))
})

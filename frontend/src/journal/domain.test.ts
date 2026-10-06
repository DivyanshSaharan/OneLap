import { expect, it } from 'vitest'
import {
  parseJournalStatus,
  parseLocal,
  parseOuting,
  parsePage,
} from './domain'
import { journalStatus, otherOwner, outing, owner } from './test-fixtures'

it('validates a completed observation separately from model output', () =>
  expect(parseOuting(outing)).toEqual(outing))
it.each([
  { observation: '' },
  { observation: ' padded ' },
  { observation: 'a'.repeat(1001) },
  { observation: 'hidden\u200btext' },
  { id: 'not-an-id' },
  { location: 'private' },
  { recorded_at: '2026-02-30T00:00:00.000Z' },
  { outcome: 'tracked' },
  { feedback: 5 },
])('rejects invalid user records %j', (changes) =>
  expect(() => parseOuting({ ...outing, ...changes })).toThrow(),
)
it('supports a multiline human note as plain text', () =>
  expect(
    parseOuting({
      ...outing,
      observation: 'Soft shadow.\nRough surface <not an HTML element>.',
    }).observation,
  ).toContain('\n'))
it('permits empty notes for stopped/skipped outings, not completed ones', () => {
  for (const outcome of ['stopped', 'skipped'])
    expect(
      parseOuting({ ...outing, outcome, observation: '' }).observation,
    ).toBe('')
})
it('does not accept synced notes without an owner', () =>
  expect(() =>
    parseLocal({
      version: 1,
      kind: 'entry',
      id: outing.id,
      owner_id: null,
      stage: 'synced',
      entry: outing,
    }),
  ).toThrow())
it('does not accept note content inside deletion markers', () =>
  expect(() =>
    parseLocal({
      version: 1,
      kind: 'delete',
      id: outing.id,
      owner_id: owner,
      entry: outing,
    }),
  ).toThrow())
it('requires configured status to expose a valid owner', () => {
  expect(parseJournalStatus(journalStatus)).toEqual(journalStatus)
  expect(() =>
    parseJournalStatus({ ...journalStatus, owner_id: null }),
  ).toThrow()
})
it('rejects pages for another journal and unverified-source labels', () => {
  const page = {
    owner_id: owner,
    entries: [
      {
        entry: outing,
        received_at: outing.recorded_at,
        mission_source: 'client_submitted',
      },
    ],
    next_after: null,
  }
  expect(parsePage(page, owner).entries).toHaveLength(1)
  expect(() => parsePage(page, otherOwner)).toThrow()
  expect(() =>
    parsePage(
      {
        ...page,
        entries: [
          { ...page.entries[0], mission_source: 'verified_model_output' },
        ],
      },
      owner,
    ),
  ).toThrow()
})

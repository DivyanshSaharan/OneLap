import { keys, object, parseMission, type MissionResponse } from '../domain'

export type Outcome = 'completed' | 'stopped' | 'skipped'
export type Feedback = 'useful' | 'too_difficult' | 'not_for_me' | null
export interface Outing {
  id: string
  mission: MissionResponse
  outcome: Outcome
  observation: string
  feedback: Feedback
  recorded_at: string
}
export interface EntryRecord {
  version: 1
  kind: 'entry'
  id: string
  owner_id: string | null
  stage: 'pending' | 'synced'
  entry: Outing
}
export interface DeleteRecord {
  version: 1
  kind: 'delete'
  id: string
  owner_id: string
}
export type LocalRecord = EntryRecord | DeleteRecord
export interface JournalStatus {
  enabled: boolean
  disabled_reason: string | null
  owner_id: string | null
  data_boundary: string
}
export interface CloudRecord {
  entry: Outing
  received_at: string
  mission_source: 'client_submitted'
}
export interface JournalPage {
  owner_id: string
  entries: CloudRecord[]
  next_after: string | null
}

export function identifier(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/.test(value)
  )
}
function timestamp(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value) &&
    Number.isFinite(Date.parse(value)) &&
    new Date(value).toISOString() === value
  )
}
export function parseOuting(value: unknown): Outing {
  const entry = object(value)
  keys(entry, [
    'id',
    'mission',
    'outcome',
    'observation',
    'feedback',
    'recorded_at',
  ])
  if (
    !identifier(entry.id) ||
    !['completed', 'stopped', 'skipped'].includes(entry.outcome as string) ||
    typeof entry.observation !== 'string' ||
    entry.observation !== entry.observation.trim() ||
    Array.from(entry.observation).length > 1000 ||
    /\p{C}/u.test(entry.observation.replace(/\n/g, '')) ||
    (entry.outcome === 'completed' && !entry.observation) ||
    ![null, 'useful', 'too_difficult', 'not_for_me'].includes(
      entry.feedback as null | string,
    ) ||
    !timestamp(entry.recorded_at)
  )
    throw new Error('invalid_outing')
  const mission = parseMission(entry.mission)
  if (!identifier(mission.id) || Array.from(mission.safety_note).length > 280)
    throw new Error('invalid_outing')
  return value as Outing
}
export function parseLocal(value: unknown): LocalRecord {
  const row = object(value)
  if (row.kind === 'entry') {
    keys(row, ['version', 'kind', 'id', 'owner_id', 'stage', 'entry'])
    const entry = parseOuting(row.entry)
    if (
      row.id !== entry.id ||
      !['pending', 'synced'].includes(row.stage as string) ||
      !(row.owner_id === null || identifier(row.owner_id)) ||
      (row.stage === 'synced' && row.owner_id === null)
    )
      throw new Error('invalid_outbox')
  } else if (row.kind === 'delete') {
    keys(row, ['version', 'kind', 'id', 'owner_id'])
    if (!identifier(row.id) || !identifier(row.owner_id))
      throw new Error('invalid_outbox')
  } else throw new Error('invalid_outbox')
  if (row.version !== 1) throw new Error('invalid_outbox')
  return value as LocalRecord
}
export function parseJournalStatus(value: unknown): JournalStatus {
  const status = object(value)
  keys(status, ['enabled', 'disabled_reason', 'owner_id', 'data_boundary'])
  if (
    typeof status.enabled !== 'boolean' ||
    typeof status.data_boundary !== 'string' ||
    status.data_boundary.length > 500 ||
    (status.enabled
      ? status.disabled_reason !== null || !identifier(status.owner_id)
      : typeof status.disabled_reason !== 'string' || status.owner_id !== null)
  )
    throw new Error('invalid_response')
  return value as JournalStatus
}
export function parsePage(value: unknown, owner: string): JournalPage {
  const page = object(value)
  keys(page, ['owner_id', 'entries', 'next_after'])
  if (
    page.owner_id !== owner ||
    !Array.isArray(page.entries) ||
    page.entries.length > 20 ||
    !(page.next_after === null || identifier(page.next_after))
  )
    throw new Error('invalid_response')
  const ids = new Set<string>()
  for (const value of page.entries) {
    const record = object(value)
    keys(record, ['entry', 'received_at', 'mission_source'])
    const entry = parseOuting(record.entry)
    if (
      !timestamp(record.received_at) ||
      record.mission_source !== 'client_submitted' ||
      ids.has(entry.id)
    )
      throw new Error('invalid_response')
    ids.add(entry.id)
  }
  if (
    page.next_after !== null &&
    (page.entries.length !== 20 ||
      page.next_after !== (page.entries[19] as CloudRecord).entry.id)
  )
    throw new Error('invalid_response')
  return value as JournalPage
}

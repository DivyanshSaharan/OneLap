import { mission } from '../test/fixtures'
import type { JournalStatus, Outing } from './domain'

export const owner = '11111111-1111-4111-8111-111111111111'
export const otherOwner = '22222222-2222-4222-8222-222222222222'
export const outing: Outing = {
  id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  mission,
  outcome: 'completed',
  observation: 'I noticed a soft shadow on a rough surface.',
  feedback: 'useful',
  recorded_at: '2026-10-06T14:00:00.000Z',
}
export const journalStatus: JournalStatus = {
  enabled: true,
  disabled_reason: null,
  owner_id: owner,
  data_boundary: 'Explicit sync sends observations to Atlas. No AI calls.',
}

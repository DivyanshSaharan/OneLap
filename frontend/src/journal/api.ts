import { ApiError, privateRequest } from '../api'
import { keys, object } from '../domain'
import {
  identifier,
  parseJournalStatus,
  parsePage,
  type LocalRecord,
} from './domain'

export async function getJournalStatus(token: string) {
  try {
    return parseJournalStatus(
      await privateRequest('/api/journal/status', token),
    )
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('invalid_response')
  }
}
export async function getJournalPage(
  token: string,
  owner: string,
  after: string | null,
) {
  if (!identifier(owner) || (after !== null && !identifier(after)))
    throw new ApiError('invalid_response')
  try {
    return parsePage(
      await privateRequest(
        `/api/journal/entries${after ? `?after=${after}` : ''}`,
        token,
        undefined,
        'GET',
        owner,
      ),
      owner,
    )
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('invalid_response')
  }
}
export async function sendRecord(
  token: string,
  owner: string,
  row: LocalRecord,
) {
  if (!identifier(owner) || row.owner_id !== owner)
    throw new ApiError('journal_owner_mismatch')
  const deleting = row.kind === 'delete'
  const result = object(
    await privateRequest(
      deleting ? `/api/journal/entries/${row.id}` : '/api/journal/entries',
      token,
      deleting ? undefined : { owner_id: owner, entry: row.entry },
      deleting ? 'DELETE' : 'POST',
      deleting ? owner : undefined,
    ),
  )
  keys(result, ['owner_id', 'id', 'status'])
  if (
    result.owner_id !== owner ||
    result.id !== row.id ||
    result.status !== (deleting ? 'deleted' : 'stored')
  )
    throw new ApiError('invalid_response')
}

export const journalReasons: Record<string, string> = {
  journal_disabled:
    'Atlas sync is switched off. You can still save observations on this device.',
  atlas_sharing_not_approved:
    'Atlas data sharing has not been approved on the server.',
  journal_not_configured:
    'The server needs an Atlas connection URI; the personal journal ID is automatic.',
  journal_dependencies_missing:
    'Install the optional journal dependencies on the server.',
  journal_owner_mismatch:
    'This change belongs to another journal. Reconnect to its original owner; it was not reassigned.',
  journal_entry_conflict:
    'That ID already holds different content. It was not overwritten. Keep your local note and inspect the conflict.',
  journal_entry_deleted:
    'This entry was deleted in Atlas and cannot be uploaded again. Your local copy is kept; remove it here when ready.',
  journal_unavailable:
    'Atlas could not confirm this action. It may have been processed. Pending changes are kept; an explicit later sync uses the same IDs.',
  unauthorized:
    'Private access was not accepted. Reconnect before synchronizing.',
  request_rate_limited:
    'Journal request limit reached. Pending changes remain saved. Wait a minute before another sync.',
  request_too_large:
    'This note and mission exceed the API size limit. The local record was kept.',
}
export function journalError(error: unknown) {
  return error instanceof ApiError && journalReasons[error.code]
    ? journalReasons[error.code]
    : 'The journal action could not be confirmed. Nothing was automatically retried or marked synced. Check your saved entries before trying again.'
}

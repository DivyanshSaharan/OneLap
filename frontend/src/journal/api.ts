import { ApiError, privateRequest } from '../api'
import { keys, object } from '../domain'
import {
  parseFollowUp,
  parseFollowUpStatus,
  identifier,
  parseJournalStatus,
  parsePage,
  type LocalRecord,
  type FollowUpStatus,
  type FollowUpSuggestion,
} from './domain'

export async function getFollowUpStatus(
  token: string,
): Promise<FollowUpStatus> {
  try {
    return parseFollowUpStatus(
      await privateRequest('/api/followups/status', token),
    )
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('invalid_response')
  }
}

export async function createFollowUp(
  token: string,
  owner: string,
  sourceId: string,
  contextIds: string[],
): Promise<FollowUpSuggestion> {
  if (
    !identifier(owner) ||
    !identifier(sourceId) ||
    contextIds.length > 2 ||
    contextIds.some((id) => !identifier(id) || id === sourceId) ||
    new Set(contextIds).size !== contextIds.length
  )
    throw new ApiError('invalid_response')
  const expectedIds = [sourceId, ...contextIds]
  try {
    return parseFollowUp(
      await privateRequest(
        '/api/followups',
        token,
        { source_id: sourceId, context_ids: contextIds },
        'POST',
        owner,
      ),
      expectedIds,
    )
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('invalid_response')
  }
}

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
  local_access_only:
    'Token-free access works only on this laptop through localhost. A non-local server needs protected access.',
  provider_unavailable: 'The model provider is not available right now.',
  provider_failed_restart_required:
    'The model request failed. It may have been processed; no automatic retry was made. Check the server before trying again.',
  provider_model_mismatch:
    'The configured model did not match OneLap’s expected model. No output was accepted.',
  generation_in_progress:
    'Another model request is still running. Wait before trying again.',
  input_token_limit:
    'The selected notes are too large for one request. Choose fewer or shorter notes.',
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
  reflection_sharing_not_approved:
    'The server has not enabled sending selected notes to Qwen.',
  followup_repeated_mission:
    'The suggested activity repeated a recent one, so it was not offered.',
  followup_source_needs_observation:
    'Choose a completed outing with a saved observation.',
  followup_context_must_precede_source:
    'Choose context notes recorded before the main observation.',
  journal_source_not_found:
    'One of the selected notes is no longer available in this Atlas journal. Reload the cloud journal and choose again.',
  hosted_requests_disabled:
    'Qwen requests are switched off on the server. No reflection request was sent.',
  data_sharing_not_approved:
    'Hosted model data sharing has not been approved on the server.',
  budget_not_approved:
    'A model spending limit has not been approved on the server.',
  provider_not_configured:
    'The Tinker service has not been configured on the server.',
  provider_dependencies_missing:
    'The server needs its optional Tinker dependencies installed.',
  budget_exhausted:
    'The estimated model-spend limit has been reached. Your saved notes remain available.',
  model_request_limit_reached:
    'The model-request limit has been reached. Your saved notes remain available.',
  provider_restart_required:
    'A previous provider failure requires the server to be checked and restarted.',
  invalid_model_output:
    'Qwen did not return a usable reflection and mission. No substitute was created.',
}
export function journalError(error: unknown) {
  return error instanceof ApiError && journalReasons[error.code]
    ? journalReasons[error.code]
    : 'The journal action could not be confirmed. Nothing was automatically retried or marked synced. Check your saved entries before trying again.'
}

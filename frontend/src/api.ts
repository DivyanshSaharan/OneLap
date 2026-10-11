import { parseMission, parseStatus, type MissionRequest } from './domain'

export class ApiError extends Error {
  constructor(public readonly code: string) {
    super(code)
  }
}

let cookieSession = false
let csrfToken: string | null = null
let sessionOwner: string | null = null
let sessionRevision = 0

// Only the CSRF token is held in memory. The opaque session cookie is HttpOnly.
export function setSessionTransport(
  enabled: boolean,
  csrf: string | null,
  owner: string | null,
) {
  cookieSession = enabled
  csrfToken = csrf
  sessionOwner = owner
  ++sessionRevision
}

const explanations: Record<string, string> = {
  sign_in_required:
    'Sign in again to use your cloud journal. Saved notes remain on this device.',
  session_changed:
    'The signed-in account changed. Reconnect before continuing.',
  google_sign_in_failed:
    'Google sign-in could not be verified. Start sign-in again.',
  auth_challenge_invalid: 'This sign-in attempt expired. Start sign-in again.',
  auth_challenge_used:
    'This sign-in attempt was already used. Start a fresh one.',
  auth_csrf_rejected:
    'Your session changed. Refresh sign-in before trying again.',
  auth_origin_rejected:
    'This website address is not enabled for sign-in on the server.',
  auth_storage_unavailable:
    'Sign-in storage is unavailable. No cloud access was granted.',
  google_widget_unavailable:
    'Google sign-in could not load. Check your connection or browser settings.',
  private_access_not_configured:
    'The private API is not configured yet. Set an access token on the server before connecting.',
  unauthorized:
    'That access token was not accepted. Check it and connect again.',
  local_access_only:
    'Token-free access works only on this laptop through localhost. A non-local server needs protected access.',
  hosted_requests_disabled:
    'Qwen requests are switched off on the server. No mission request was sent to the model.',
  data_sharing_not_approved:
    'Hosted data sharing has not been approved on the server.',
  budget_not_approved: 'A model spending limit has not been approved yet.',
  atlas_budget_not_approved:
    'OneLap’s shared spending setup has not been approved yet. New missions are paused.',
  budget_import_required:
    'Earlier model spending needs to be added to OneLap’s records before new missions can be created.',
  budget_import_below_known_usage:
    'OneLap’s spending setup is missing some earlier usage. New missions are paused until it is corrected.',
  budget_import_below_local_ledger:
    'The spending setup is below this server’s recorded usage. New missions are paused until it is corrected.',
  budget_import_mismatch:
    'OneLap’s spending settings do not match its saved records. New missions are paused until they are corrected.',
  budget_ledger_scope_mismatch:
    'OneLap’s spending records belong to a different setup. New missions are paused until the server is checked.',
  budget_ledger_not_configured:
    'OneLap’s spending records are not connected yet. New missions are paused until the server setup is completed.',
  budget_reservation_conflict:
    'OneLap found conflicting spending records. New missions are paused until the server is checked.',
  provider_not_configured:
    'The Tinker key has not been configured on the server.',
  provider_dependencies_missing:
    'The server needs its optional Tinker dependencies installed.',
  budget_exhausted:
    'The estimated model-spend limit has been reached. Your saved mission is still available.',
  model_request_limit_reached:
    'The model-request limit has been reached. Your saved mission is still available.',
  request_rate_limited:
    'Too many generation attempts. Wait a minute before trying again.',
  generation_in_progress:
    'Another generation is still running. Wait before making another request.',
  provider_restart_required:
    'A previous provider failure requires the server to be checked and restarted.',
  provider_failed_restart_required:
    'The model request failed. It may still have been processed; no automatic retry was made. Check the server before trying again.',
  mission_constraint_mismatch:
    'The model changed your outing preferences. That mission was rejected.',
  mission_policy_rejected:
    'The generated task failed the application checks. It was not saved as a mission.',
  invalid_model_output:
    'The model did not return a usable mission. No substitute was created.',
  invalid_response:
    'The API returned an unexpected response. It was not saved.',
  budget_ledger_busy:
    'Spending admission is locked. Check the server rather than repeatedly retrying.',
  budget_ledger_unavailable:
    'The server could not verify its spending ledger. No new mission was admitted.',
  request_timeout:
    'The reply took too long. The server may still be processing the request. No automatic retry was made.',
  network_unavailable:
    'The API could not be reached. A generation request may have been processed; do not immediately retry.',
  offline:
    'You are offline. Open your saved mission; generation needs a connection.',
}

export function explain(error: unknown): string {
  const code = error instanceof ApiError ? error.code : 'invalid_response'
  return Object.hasOwn(explanations, code)
    ? explanations[code]
    : 'The API could not complete this action. No substitute mission was created.'
}

export async function privateRequest(
  path: string,
  token: string,
  body?: unknown,
  method: 'GET' | 'POST' | 'DELETE' = body ? 'POST' : 'GET',
  owner?: string,
): Promise<unknown> {
  if (!navigator.onLine) throw new ApiError('offline')
  const authRequest = path.startsWith('/api/auth/')
  const revision = sessionRevision
  if (!authRequest && cookieSession && owner && owner !== sessionOwner)
    throw new ApiError('session_changed')
  const controller = new AbortController()
  const timeout = window.setTimeout(
    () => controller.abort(),
    path === '/api/missions' || path === '/api/followups' ? 75_000 : 15_000,
  )
  try {
    const response = await fetch(path, {
      method,
      headers: {
        ...(token && !cookieSession
          ? { Authorization: `Bearer ${token}` }
          : {}),
        ...(cookieSession && csrfToken && method !== 'GET'
          ? { 'X-OneLap-CSRF': csrfToken }
          : {}),
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(owner ? { 'X-OneLap-Journal-Owner': owner } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: 'no-store',
      credentials: authRequest || cookieSession ? 'same-origin' : 'omit',
      signal: controller.signal,
    })
    let result: unknown
    try {
      result = await response.json()
    } catch {
      throw new ApiError(
        controller.signal.aborted ? 'request_timeout' : 'invalid_response',
      )
    }
    if (!response.ok) {
      const code =
        result &&
        typeof result === 'object' &&
        'error' in result &&
        typeof result.error === 'string'
          ? result.error
          : 'invalid_response'
      if (
        !authRequest &&
        cookieSession &&
        ['sign_in_required', 'auth_csrf_rejected'].includes(code)
      )
        window.dispatchEvent(new Event('onelap:session-expired'))
      throw new ApiError(code)
    }
    if (!authRequest && cookieSession && revision !== sessionRevision)
      throw new ApiError('session_changed')
    return result
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(
      controller.signal.aborted ? 'request_timeout' : 'network_unavailable',
    )
  } finally {
    window.clearTimeout(timeout)
  }
}

export async function getStatus(token: string) {
  try {
    return parseStatus(await privateRequest('/api/model/status', token))
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('invalid_response')
  }
}

export async function generateMission(token: string, input: MissionRequest) {
  let result
  try {
    result = parseMission(await privateRequest('/api/missions', token, input))
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('invalid_response')
  }
  for (const key of ['minutes', 'setting', 'conditions', 'focus'] as const) {
    if (result.mission[key] !== input[key])
      throw new ApiError('mission_constraint_mismatch')
  }
  return result
}

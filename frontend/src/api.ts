import { parseMission, parseStatus, type MissionRequest } from './domain'

export class ApiError extends Error {
  constructor(public readonly code: string) {
    super(code)
  }
}

const explanations: Record<string, string> = {
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
  return (
    explanations[code] ??
    'The API could not complete this action. No substitute mission was created.'
  )
}

export async function privateRequest(
  path: string,
  token: string,
  body?: unknown,
  method: 'GET' | 'POST' | 'DELETE' = body ? 'POST' : 'GET',
  owner?: string,
): Promise<unknown> {
  if (!navigator.onLine) throw new ApiError('offline')
  const controller = new AbortController()
  const timeout = window.setTimeout(
    () => controller.abort(),
    path === '/api/missions' || path === '/api/followups' ? 75_000 : 15_000,
  )
  try {
    const response = await fetch(path, {
      method,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(owner ? { 'X-OneLap-Journal-Owner': owner } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: 'no-store',
      credentials: 'omit',
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
      throw new ApiError(code)
    }
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

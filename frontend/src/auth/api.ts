import { ApiError, privateRequest } from '../api'
import { keys, object } from '../domain'
import { identifier } from '../journal/domain'

export interface Session {
  enabled: boolean
  client_id: string | null
  owner_id: string | null
  csrf: string | null
}

export function parseSession(value: unknown): Session {
  const session = object(value)
  keys(session, ['enabled', 'client_id', 'owner_id', 'csrf'])
  if (
    typeof session.enabled !== 'boolean' ||
    (session.enabled
      ? typeof session.client_id !== 'string' ||
        !session.client_id.endsWith('.apps.googleusercontent.com')
      : session.client_id !== null ||
        session.owner_id !== null ||
        session.csrf !== null) ||
    (session.owner_id === null
      ? session.csrf !== null
      : !identifier(session.owner_id) ||
        typeof session.csrf !== 'string' ||
        !/^[a-zA-Z0-9_-]{43}$/.test(session.csrf))
  )
    throw new ApiError('invalid_response')
  return session as unknown as Session
}

export async function getSession() {
  return parseSession(await privateRequest('/api/auth/session', ''))
}

export async function getChallenge() {
  const result = object(await privateRequest('/api/auth/challenge', ''))
  keys(result, ['nonce', 'csrf'])
  if (
    typeof result.nonce !== 'string' ||
    typeof result.csrf !== 'string' ||
    !/^[a-zA-Z0-9_-]{43}$/.test(result.nonce) ||
    !/^[a-zA-Z0-9_-]{43}$/.test(result.csrf)
  )
    throw new ApiError('invalid_response')
  return { nonce: result.nonce, csrf: result.csrf }
}

export async function login(credential: string, csrf: string) {
  return parseSession(
    await privateRequest('/api/auth/google', '', { credential, csrf }),
  )
}

export async function logout() {
  const result = object(
    await privateRequest('/api/auth/logout', '', {}, 'POST'),
  )
  keys(result, ['status'])
  if (result.status !== 'signed_out') throw new ApiError('invalid_response')
}

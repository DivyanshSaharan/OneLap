import { describe, expect, it } from 'vitest'
import { parseMission, parseStatus } from './domain'
import { mission, status } from './test/fixtures'

describe('mission response contract', () => {
  it('accepts a hash-bound adapter without exposing its private path', () => {
    const response = {
      ...mission,
      generation: {
        ...mission.generation,
        target: 'adapter',
        checkpoint_sha256: 'a'.repeat(64),
        training_dataset_sha256: 'b'.repeat(64),
      },
    }
    expect(parseMission(response)).toEqual(response)
  })
  it.each([
    { target: 'adapter' },
    {
      target: 'adapter',
      checkpoint_sha256: 'bad',
      training_dataset_sha256: 'b'.repeat(64),
    },
    { target: 'base', checkpoint_sha256: 'a'.repeat(64) },
  ])('rejects inconsistent adapter provenance', (changes) => {
    expect(() =>
      parseMission({
        ...mission,
        generation: { ...mission.generation, ...changes },
      }),
    ).toThrow()
  })
  it('accepts the current backend response', () =>
    expect(parseMission(mission)).toEqual(mission))
  it.each(['follow-up-v1', 'follow-up-v2'])(
    'accepts a known follow-up prompt version %s',
    (prompt_version) => {
      const response = {
        ...mission,
        generation: { ...mission.generation, prompt_version },
      }
      expect(parseMission(response)).toEqual(response)
    },
  )
  it.each([
    null,
    [],
    {},
    { ...mission, id: 'not-uuid' },
    { ...mission, token: 'private' },
    { ...mission, safety_note: '<script>' },
    { ...mission, generation: { ...mission.generation, target: 'tuned' } },
    {
      ...mission,
      generation: { ...mission.generation, prompt_version: 'unknown-version' },
    },
    {
      ...mission,
      generation: { ...mission.generation, model: 'another-model' },
    },
  ])('rejects malformed or incorrectly attributed responses', (value) => {
    expect(() => parseMission(value)).toThrow('invalid_response')
  })
  it.each([
    ['title', ''],
    ['title', ' leading'],
    ['title', 'a'.repeat(81)],
    ['instruction', 'a'.repeat(281)],
    ['instruction', 'newline\ntext'],
    ['remember', 'invisible\u200btext'],
    ['remember', '`markup`'],
    ['minutes', '15'],
    ['minutes', 5],
    ['setting', 'precise-location'],
    ['conditions', 'unknown'],
    ['focus', 'unknown'],
    ['requires_camera', 0],
    ['requires_camera', true],
    ['phone_use', 'recording'],
  ])('rejects invalid mission field %s', (key, value) => {
    expect(() =>
      parseMission({
        ...mission,
        mission: { ...mission.mission, [key]: value },
      }),
    ).toThrow()
  })
})

describe('status response contract', () => {
  it('accepts an explicitly selected adapter', () => {
    expect(parseStatus({ ...status, target: 'adapter' }).target).toBe('adapter')
  })
  it('accepts current backend status', () =>
    expect(parseStatus(status)).toEqual(status))
  it.each([
    { ...status, enabled: 'yes' },
    { ...status, target: 'tuned' },
    { ...status, estimated_reserved_usd: NaN },
    { ...status, approved_budget_usd: -1 },
    { ...status, reserved_requests: 1.5 },
    { ...status, maximum_requests: '20' },
    { ...status, disabled_reason: 'disabled' },
    { ...status, key: 'private' },
  ])('rejects invalid status', (value) =>
    expect(() => parseStatus(value)).toThrow(),
  )
})

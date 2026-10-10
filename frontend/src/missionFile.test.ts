import { expect, it, vi } from 'vitest'
import {
  MAX_MISSION_FILE_BYTES,
  parseMissionFile,
  readMissionFile,
} from './missionFile'
import { mission } from './test/fixtures'

export function missionFile(
  text = JSON.stringify(mission),
  name = 'mission.json',
) {
  const file = new File([text], name, { type: 'application/json' })
  Object.defineProperty(file, 'text', {
    value: vi.fn().mockResolvedValue(text),
  })
  return file
}

it('opens a single validated mission, without requiring a backend', async () => {
  expect(parseMissionFile(JSON.stringify(mission))).toEqual(mission)
  expect(await readMissionFile(missionFile())).toEqual(mission)
  expect(parseMissionFile('\uFEFF' + JSON.stringify(mission))).toEqual(mission)
})

it.each([
  '',
  'not json',
  JSON.stringify({ mission }),
  JSON.stringify([mission]),
  JSON.stringify({ ...mission, unexpected: 'private-sentinel' }),
  JSON.stringify({
    ...mission,
    generation: { ...mission.generation, target: 'fine-tuned' },
  }),
  JSON.stringify({
    ...mission,
    mission: { ...mission.mission, requires_camera: true },
  }),
  JSON.stringify({
    ...mission,
    mission: { ...mission.mission, instruction: 'Use a camera.' },
  }),
  JSON.stringify({
    ...mission,
    mission: { ...mission.mission, instruction: '<script>bad</script>' },
  }),
])('rejects unsupported file content with a generic error', (text) => {
  expect(() => parseMissionFile(text)).toThrow('mission_file_invalid')
})

it.each(['id', 'instruction', 'generation', 'provider'])(
  'rejects duplicate or escaped duplicate JSON keys: %s',
  (key) => {
    const text = JSON.stringify(mission)
    const pattern = `"${key}":`
    const duplicated = text.replace(pattern, `"${key}":null,${pattern}`)
    expect(() => parseMissionFile(duplicated)).toThrow('mission_file_invalid')
    const escaped = text.replace(
      pattern,
      `"\\u${key.charCodeAt(0).toString(16).padStart(4, '0')}${key.slice(1)}":null,${pattern}`,
    )
    expect(() => parseMissionFile(escaped)).toThrow('mission_file_invalid')
  },
)

it('does not mistake punctuation or quoted keys inside values for duplicate fields', () => {
  const changed = {
    ...mission,
    safety_note: 'A quoted "id": example with braces { } [ ] is only text.',
  }
  expect(parseMissionFile(JSON.stringify(changed))).toEqual(changed)
})

it('bounds file size before reading and accepts upper-case JSON extensions', async () => {
  const file = missionFile('x'.repeat(MAX_MISSION_FILE_BYTES + 1))
  await expect(readMissionFile(file)).rejects.toThrow('mission_file_invalid')
  expect(file.text).not.toHaveBeenCalled()
  expect(
    await readMissionFile(missionFile(JSON.stringify(mission), 'MISSION.JSON')),
  ).toEqual(mission)
  await expect(readMissionFile(missionFile('', 'empty.json'))).rejects.toThrow()
  await expect(
    readMissionFile(missionFile(JSON.stringify(mission), 'not-json.txt')),
  ).rejects.toThrow()
})

it('bounds UTF-8 bytes and masks file-read errors', async () => {
  expect(() => parseMissionFile('é'.repeat(MAX_MISSION_FILE_BYTES))).toThrow(
    'mission_file_invalid',
  )
  const file = missionFile()
  vi.mocked(file.text).mockRejectedValue(new Error('private-sentinel'))
  await expect(readMissionFile(file)).rejects.toThrow('mission_file_invalid')
})

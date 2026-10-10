import { parseMission, type MissionResponse } from './domain'

export const MAX_MISSION_FILE_BYTES = 16_384

const prohibited =
  /\b(?:photograph\w*|photos?|camera|selfie\w*|record\w*|screens?|gps|maps?|touch\w*|pluck\w*|collect\w*|taste\w*|eat|feed|climb\w*|strangers?)\b|\b(?:pick\s+up|cross\s+(?:a\s+|the\s+)?road|close\s+your\s+eyes)\b|https?:\/\/|www\./i

function parseUniqueJson(text: string): unknown {
  const parsed: unknown = JSON.parse(text)
  const objects: (Set<string> | null)[] = []
  // Tokenize whole strings first, so braces or colons inside values aren't keys.
  for (const token of text.matchAll(/"(?:\\.|[^"\\])*"(\s*:)?|[{}[\]]/g)) {
    const symbol = token[0][0]
    if (symbol === '{') objects.push(new Set())
    else if (symbol === '[') objects.push(null)
    else if (symbol === '}' || symbol === ']') objects.pop()
    else if (token[1]) {
      const keys = objects.at(-1)
      const key: string = JSON.parse(token[0].slice(0, -token[1].length))
      if (!keys || keys.has(key)) throw new Error('mission_file_invalid')
      keys.add(key)
    }
  }
  return parsed
}

export function parseMissionFile(text: string): MissionResponse {
  try {
    if (new TextEncoder().encode(text).length > MAX_MISSION_FILE_BYTES)
      throw new Error('mission_file_invalid')
    const response = parseMission(parseUniqueJson(text.replace(/^\uFEFF/, '')))
    const mission = response.mission
    if (
      prohibited.test(
        [mission.title, mission.instruction, mission.remember].join(' '),
      )
    )
      throw new Error('mission_file_invalid')
    return response
  } catch {
    throw new Error('mission_file_invalid')
  }
}

export async function readMissionFile(file: File): Promise<MissionResponse> {
  if (
    !file.name.toLowerCase().endsWith('.json') ||
    file.size === 0 ||
    file.size > MAX_MISSION_FILE_BYTES
  )
    throw new Error('mission_file_invalid')
  try {
    return parseMissionFile(await file.text())
  } catch {
    throw new Error('mission_file_invalid')
  }
}

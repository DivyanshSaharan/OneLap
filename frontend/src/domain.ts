export type Minutes = 10 | 15 | 20
export type Setting = 'courtyard' | 'park' | 'familiar_walking_area'
export type Conditions = 'daylight' | 'evening'
export type Focus = 'light' | 'textures' | 'sounds' | 'general'

export interface MissionRequest {
  minutes: Minutes
  setting: Setting
  conditions: Conditions
  focus: Focus
}

export interface MissionResponse {
  id: string
  mission: MissionRequest & {
    title: string
    instruction: string
    remember: string
    requires_camera: false
    phone_use: 'none_during_outing'
  }
  generation: {
    provider: 'tinker'
    model: 'Qwen/Qwen3.5-4B'
    target: 'base'
    prompt_version: 'mission-v1'
  }
  safety_note: string
}

export interface ProviderStatus {
  model: string
  target: 'base'
  enabled: boolean
  disabled_reason: string | null
  estimated_reserved_usd: number
  approved_budget_usd: number
  reserved_requests: number
  maximum_requests: number
  data_boundary: string
}

const settings: Setting[] = ['courtyard', 'park', 'familiar_walking_area']
const conditions: Conditions[] = ['daylight', 'evening']
const focuses: Focus[] = ['light', 'textures', 'sounds', 'general']

export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('invalid_response')
  return value as Record<string, unknown>
}

export function keys(value: Record<string, unknown>, expected: string[]): void {
  if (
    Object.keys(value).length !== expected.length ||
    expected.some((key) => !(key in value))
  ) {
    throw new Error('invalid_response')
  }
}

function text(value: unknown, max: number): value is string {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    value.length <= max &&
    value === value.trim() &&
    !/[\p{C}<>`]/u.test(value)
  )
}

export function parseMission(value: unknown): MissionResponse {
  const response = object(value)
  keys(response, ['id', 'mission', 'generation', 'safety_note'])
  const mission = object(response.mission)
  keys(mission, [
    'title',
    'instruction',
    'remember',
    'minutes',
    'setting',
    'conditions',
    'focus',
    'requires_camera',
    'phone_use',
  ])
  const generation = object(response.generation)
  keys(generation, ['provider', 'model', 'target', 'prompt_version'])
  if (
    typeof response.id !== 'string' ||
    !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(response.id) ||
    !text(mission.title, 80) ||
    !text(mission.instruction, 280) ||
    !text(mission.remember, 160) ||
    ![10, 15, 20].includes(mission.minutes as number) ||
    !settings.includes(mission.setting as Setting) ||
    !conditions.includes(mission.conditions as Conditions) ||
    !focuses.includes(mission.focus as Focus) ||
    mission.requires_camera !== false ||
    mission.phone_use !== 'none_during_outing' ||
    generation.provider !== 'tinker' ||
    generation.model !== 'Qwen/Qwen3.5-4B' ||
    generation.target !== 'base' ||
    generation.prompt_version !== 'mission-v1' ||
    !text(response.safety_note, 400)
  ) {
    throw new Error('invalid_response')
  }
  return value as MissionResponse
}

export function parseStatus(value: unknown): ProviderStatus {
  const status = object(value)
  keys(status, [
    'model',
    'target',
    'enabled',
    'disabled_reason',
    'estimated_reserved_usd',
    'approved_budget_usd',
    'reserved_requests',
    'maximum_requests',
    'data_boundary',
  ])
  const numbers = [
    'estimated_reserved_usd',
    'approved_budget_usd',
    'reserved_requests',
    'maximum_requests',
  ]
  if (
    status.model !== 'Qwen/Qwen3.5-4B' ||
    status.target !== 'base' ||
    typeof status.enabled !== 'boolean' ||
    !(status.disabled_reason === null || text(status.disabled_reason, 80)) ||
    (status.enabled && status.disabled_reason !== null) ||
    numbers.some(
      (key) =>
        typeof status[key] !== 'number' ||
        !Number.isFinite(status[key]) ||
        (status[key] as number) < 0,
    ) ||
    !Number.isInteger(status.reserved_requests) ||
    !Number.isInteger(status.maximum_requests) ||
    !text(status.data_boundary, 500)
  )
    throw new Error('invalid_response')
  return value as ProviderStatus
}

export const settingLabels: Record<Setting, string> = {
  courtyard: 'Courtyard',
  park: 'Park',
  familiar_walking_area: 'Familiar walking area',
}

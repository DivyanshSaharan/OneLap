import type { MissionRequest, MissionResponse, ProviderStatus } from '../domain'

export const input: MissionRequest = {
  minutes: 15,
  setting: 'courtyard',
  conditions: 'evening',
  focus: 'general',
}
export const mission: MissionResponse = {
  id: '851c423d-4314-4c84-a80c-9e17f590d30b',
  mission: {
    ...input,
    title: 'Notice a small contrast',
    instruction:
      'Within your familiar area, notice two contrasting surfaces if you find them.',
    remember: 'What difference stood out?',
    requires_camera: false,
    phone_use: 'none_during_outing',
  },
  generation: {
    provider: 'tinker',
    model: 'Qwen/Qwen3.5-4B',
    target: 'base',
    prompt_version: 'mission-v1',
  },
  safety_note:
    'Skip or stop if conditions are unsuitable. This is not navigation or a safety assessment.',
}
export const status: ProviderStatus = {
  model: 'Qwen/Qwen3.5-4B',
  target: 'base',
  enabled: true,
  disabled_reason: null,
  estimated_reserved_usd: 0,
  approved_budget_usd: 0.1,
  reserved_requests: 0,
  maximum_requests: 20,
  data_boundary:
    'Mission inputs go to Tinker. No raw photos or audio are accepted.',
}

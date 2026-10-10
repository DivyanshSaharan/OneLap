import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError } from './api'
import { mission, status } from './test/fixtures'

const mocks = vi.hoisted(() => ({
  load: vi.fn(),
  save: vi.fn(),
  clear: vi.fn(),
  getStatus: vi.fn(),
  generate: vi.fn(),
}))
vi.mock('./storage', async (original) => ({
  ...(await original<typeof import('./storage')>()),
  loadMission: mocks.load,
  saveMission: mocks.save,
  clearMission: mocks.clear,
}))
vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  getStatus: mocks.getStatus,
  generateMission: mocks.generate,
}))
vi.mock('./hooks/useOfflineShell', () => ({
  useOfflineShell: () => ({
    state: 'ready',
    updateAvailable: false,
    update: vi.fn(),
  }),
}))

beforeEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
  mocks.load.mockResolvedValue(null)
  mocks.save.mockResolvedValue({
    version: 1,
    response: mission,
    savedAt: new Date().toISOString(),
  })
  mocks.clear.mockResolvedValue(undefined)
  mocks.getStatus.mockResolvedValue(status)
  mocks.generate.mockResolvedValue(mission)
})

async function connect() {
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Connect to local backend' }),
    ).toBeEnabled(),
  )
  fireEvent.click(screen.getByText('Backend connection'))
  await userEvent.click(
    screen.getByRole('button', { name: 'Connect to local backend' }),
  )
  await screen.findByText('Ready')
  await userEvent.click(
    screen.getByRole('checkbox', {
      name: /these selections go to hosted Qwen/,
    }),
  )
}

it('does not call the model, check status or create a fake mission on load', async () => {
  render(<App />)
  await screen.findByText('Your outing starts here.')
  expect(mocks.getStatus).not.toHaveBeenCalled()
  expect(mocks.generate).not.toHaveBeenCalled()
  expect(
    screen.getByRole('button', { name: /Create my small outing/ }),
  ).toBeDisabled()
})
it('imports offline only after review, saves unverified provenance and makes no API request', async () => {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
  render(<App />)
  await screen.findByText('Your outing starts here.')
  fireEvent.click(screen.getByText('Use a captured mission · no model request'))
  await waitFor(() =>
    expect(screen.getByLabelText('Mission JSON file')).toBeEnabled(),
  )
  const file = new File([JSON.stringify(mission)], 'mission.json', {
    type: 'application/json',
  })
  Object.defineProperty(file, 'text', {
    value: async () => JSON.stringify(mission),
  })
  await userEvent.upload(screen.getByLabelText('Mission JSON file'), file)
  await screen.findByText('FILE PREVIEW · NOT YET SAVED')
  expect(mocks.save).not.toHaveBeenCalled()
  await userEvent.click(
    screen.getByRole('checkbox', { name: /I reviewed this unverified file/ }),
  )
  await userEvent.click(
    screen.getByRole('button', { name: 'Save imported mission' }),
  )
  await screen.findByText('Imported file · model provenance not verified')
  expect(mocks.save).toHaveBeenCalledExactlyOnceWith(mission, 'imported')
  expect(mocks.getStatus).not.toHaveBeenCalled()
  expect(mocks.generate).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: /I’m heading out/ }))
  expect(
    screen.getByText('Imported file · model provenance not verified'),
  ).toBeInTheDocument()
  expect(
    screen.queryByText('Use a captured mission · no model request'),
  ).not.toBeInTheDocument()
})

it('keeps an existing mission when saving an imported file fails', async () => {
  mocks.load.mockResolvedValue({
    version: 1,
    response: mission,
    savedAt: new Date().toISOString(),
  })
  mocks.save.mockRejectedValue(new Error('disk-full'))
  render(<App />)
  await screen.findByRole('heading', { name: mission.mission.title })
  fireEvent.click(screen.getByText('Use a captured mission · no model request'))
  const replacement = {
    ...mission,
    mission: { ...mission.mission, title: 'Replacement' },
  }
  const file = new File([JSON.stringify(replacement)], 'mission.json', {
    type: 'application/json',
  })
  Object.defineProperty(file, 'text', {
    value: async () => JSON.stringify(replacement),
  })
  await userEvent.upload(screen.getByLabelText('Mission JSON file'), file)
  await screen.findByRole('heading', { name: 'Replacement' })
  await userEvent.click(
    screen.getByRole('checkbox', { name: /I reviewed this unverified file/ }),
  )
  await userEvent.click(
    screen.getByRole('button', { name: 'Save imported mission' }),
  )
  await screen.findByText(/The import was not saved/)
  expect(
    screen.getByRole('heading', { name: mission.mission.title }),
  ).toBeInTheDocument()
  expect(
    screen.queryByText('Imported file · model provenance not verified'),
  ).not.toBeInTheDocument()
})

it('retains the imported label on restoring a previously saved file', async () => {
  mocks.load.mockResolvedValue({
    version: 1,
    source: 'imported',
    response: mission,
    savedAt: new Date().toISOString(),
  })
  render(<App />)
  await screen.findByText('Imported file · model provenance not verified')
  expect(mocks.generate).not.toHaveBeenCalled()
})

it('shows saved follow-up references offline without reading notes or copying their text', async () => {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
  const origin = {
    owner_id: '11111111-1111-4111-8111-111111111111',
    source_ids: ['aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
  }
  mocks.load.mockResolvedValue({
    version: 1,
    response: {
      ...mission,
      generation: { ...mission.generation, prompt_version: 'follow-up-v2' },
    },
    savedAt: new Date().toISOString(),
    followUpOrigin: origin,
  })
  render(<App />)
  await screen.findByRole('heading', { name: mission.mission.title })
  await userEvent.click(screen.getByText('How this was generated'))
  const references = screen.getByLabelText('Saved follow-up source references')
  expect(references).toHaveTextContent(origin.owner_id)
  expect(references).toHaveTextContent(origin.source_ids[0])
  expect(references).toHaveTextContent(
    'no copies of note text or the reflection',
  )
  expect(references).toHaveTextContent(
    'Opening this section does not fetch them',
  )
  expect(mocks.getStatus).not.toHaveBeenCalled()
  expect(mocks.generate).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: /I’m heading out/ }))
  expect(
    screen.queryByLabelText('Saved follow-up source references'),
  ).not.toBeInTheDocument()
})

it('does not invent source references for a legacy follow-up or an imported file', async () => {
  const response = {
    ...mission,
    generation: { ...mission.generation, prompt_version: 'follow-up-v2' },
  }
  mocks.load.mockResolvedValue({
    version: 1,
    response,
    savedAt: new Date().toISOString(),
  })
  const { unmount } = render(<App />)
  await screen.findByRole('heading', { name: mission.mission.title })
  await userEvent.click(screen.getByText('How this was generated'))
  expect(
    screen.getByText('Source references were not saved for this mission.'),
  ).toBeInTheDocument()
  unmount()
  mocks.load.mockResolvedValue({
    version: 1,
    response,
    savedAt: new Date().toISOString(),
    source: 'imported',
  })
  render(<App />)
  await screen.findByText('Imported file · model provenance not verified')
  expect(
    screen.queryByLabelText('Saved follow-up source references'),
  ).not.toBeInTheDocument()
  expect(mocks.generate).not.toHaveBeenCalled()
})
it('connects locally without a token and still requires hosted-selection consent', async () => {
  render(<App />)
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Connect to local backend' }),
    ).toBeEnabled(),
  )
  fireEvent.click(screen.getByText('Backend connection'))
  await userEvent.click(
    screen.getByRole('button', { name: 'Connect to local backend' }),
  )
  await screen.findByText('Ready')
  expect(
    screen.getByRole('button', { name: /Create my small outing/ }),
  ).toBeDisabled()
  expect(mocks.generate).not.toHaveBeenCalled()
  expect(mocks.getStatus).toHaveBeenCalledWith('')
})
it('shows pending work, prevents duplicate submission, saves once and exposes pocket mode', async () => {
  let resolve!: (value: typeof mission) => void
  mocks.generate.mockReturnValue(
    new Promise((done) => {
      resolve = done
    }),
  )
  render(<App />)
  await connect()
  await userEvent.click(
    screen.getByRole('button', { name: /Create my small outing/ }),
  )
  expect(
    screen.getByRole('button', { name: /Creating your mission/ }),
  ).toBeDisabled()
  expect(screen.getByLabelText('Where will you go?')).toBeDisabled()
  fireEvent.submit(
    screen
      .getByRole('button', { name: /Creating your mission/ })
      .closest('form')!,
  )
  expect(mocks.generate).toHaveBeenCalledTimes(1)
  await act(async () => resolve(mission))
  await screen.findByRole('heading', { name: 'Notice a small contrast' })
  await screen.findByText('Saved on this device · ready to reopen offline')
  expect(mocks.save).toHaveBeenCalledExactlyOnceWith(mission)
  await userEvent.click(screen.getByRole('button', { name: /I’m heading out/ }))
  expect(
    screen.queryByRole('heading', { name: 'Make room for a small lap.' }),
  ).not.toBeInTheDocument()
  expect(
    screen.getByText(/does not mark this mission complete/),
  ).toBeInTheDocument()
  expect(mocks.generate).toHaveBeenCalledTimes(1)
})
it('restores a saved mission offline without authentication or model calls', async () => {
  mocks.load.mockResolvedValue({
    version: 1,
    response: mission,
    savedAt: new Date().toISOString(),
  })
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
  render(<App />)
  await screen.findByRole('heading', { name: 'Notice a small contrast' })
  expect(screen.getByText('Device offline')).toBeInTheDocument()
  expect(mocks.generate).not.toHaveBeenCalled()
  expect(mocks.getStatus).not.toHaveBeenCalled()
  expect(
    screen.getByRole('button', { name: /Create my small outing/ }),
  ).toBeDisabled()
})
it('does not replace an existing mission with an error or fallback', async () => {
  mocks.load.mockResolvedValue({
    version: 1,
    response: mission,
    savedAt: new Date().toISOString(),
  })
  mocks.generate.mockRejectedValue(new ApiError('mission_policy_rejected'))
  render(<App />)
  await connect()
  await userEvent.click(
    screen.getByRole('button', { name: /Create my small outing/ }),
  )
  await screen.findByRole('alert')
  expect(
    screen.getByRole('heading', { name: 'Notice a small contrast' }),
  ).toBeInTheDocument()
  expect(mocks.save).not.toHaveBeenCalled()
  expect(
    screen.getByRole('button', { name: /Create my small outing/ }),
  ).toBeDisabled()
  expect(screen.getByLabelText('Server access token')).toHaveValue('')
})
it('reports storage failure without claiming offline readiness', async () => {
  mocks.save.mockRejectedValue(new Error('disk-full'))
  render(<App />)
  await connect()
  await userEvent.click(
    screen.getByRole('button', { name: /Create my small outing/ }),
  )
  await screen.findByRole('heading', { name: 'Notice a small contrast' })
  expect(
    screen.getByText('Not saved yet · keep this page open'),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: 'Try saving again' }),
  ).toBeInTheDocument()
  expect(
    screen.queryByText('Saved on this device · ready to reopen offline'),
  ).not.toBeInTheDocument()
})
it('clears local missions only after storage confirms deletion', async () => {
  mocks.load.mockResolvedValue({
    version: 1,
    response: mission,
    savedAt: new Date().toISOString(),
  })
  mocks.clear.mockRejectedValue(new Error('blocked'))
  render(<App />)
  await screen.findByRole('heading', { name: 'Notice a small contrast' })
  await userEvent.click(
    screen.getByRole('button', { name: 'Clear this device’s saved mission' }),
  )
  await screen.findByRole('alert')
  expect(
    screen.getByRole('heading', { name: 'Notice a small contrast' }),
  ).toBeInTheDocument()
})
it('keeps hosted generation off when the server reports it disabled', async () => {
  mocks.getStatus.mockResolvedValue({
    ...status,
    enabled: false,
    disabled_reason: 'hosted_requests_disabled',
  })
  render(<App />)
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Connect to local backend' }),
    ).toBeEnabled(),
  )
  fireEvent.click(screen.getByText('Backend connection'))
  await userEvent.click(
    screen.getByRole('button', { name: 'Connect to local backend' }),
  )
  await screen.findByText('Connected · generation off')
  expect(
    screen.getByRole('button', { name: /Create my small outing/ }),
  ).toBeDisabled()
  expect(mocks.generate).not.toHaveBeenCalled()
})

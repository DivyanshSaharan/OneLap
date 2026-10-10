import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { mission } from '../test/fixtures'
import { MissionImport } from './MissionImport'

function file(text = JSON.stringify(mission)) {
  const chosen = new File([text], 'mission.json', { type: 'application/json' })
  Object.defineProperty(chosen, 'text', {
    value: vi.fn().mockResolvedValue(text),
  })
  return chosen
}

async function choose(chosen = file()) {
  fireEvent.click(screen.getByText('Use a captured mission · no model request'))
  await userEvent.upload(screen.getByLabelText('Mission JSON file'), chosen)
}

it('previews locally and requires explicit review before replacing a mission', async () => {
  const accept = vi.fn().mockResolvedValue(true)
  render(<MissionImport busy={false} hasMission onImport={accept} />)
  await choose()
  await screen.findByRole('heading', { name: mission.mission.title })
  expect(accept).not.toHaveBeenCalled()
  expect(
    screen.getByText(/Model provenance is not verified/),
  ).toBeInTheDocument()
  expect(
    screen.getByText(/Saving replaces the current mission/),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: 'Save imported mission' }),
  ).toBeDisabled()
  await userEvent.click(screen.getByRole('checkbox'))
  await userEvent.click(
    screen.getByRole('button', { name: 'Save imported mission' }),
  )
  await screen.findByText(/Imported and saved on this device/)
  expect(accept).toHaveBeenCalledExactlyOnceWith(mission)
})

it('rejects bad files without changing a mission or echoing file content', async () => {
  const accept = vi.fn()
  render(<MissionImport busy={false} hasMission onImport={accept} />)
  await choose(file('{"private":"private-sentinel"}'))
  await screen.findByRole('alert')
  expect(screen.queryByText(/private-sentinel/)).not.toBeInTheDocument()
  expect(accept).not.toHaveBeenCalled()
})

it('discards a preview and resets review on a newly selected file', async () => {
  const accept = vi.fn()
  render(<MissionImport busy={false} hasMission={false} onImport={accept} />)
  await choose()
  await screen.findByRole('heading', { name: mission.mission.title })
  await userEvent.click(screen.getByRole('checkbox'))
  await userEvent.upload(screen.getByLabelText('Mission JSON file'), file())
  await screen.findByRole('heading', { name: mission.mission.title })
  expect(screen.getByRole('checkbox')).not.toBeChecked()
  await userEvent.click(
    screen.getByRole('button', { name: 'Discard file preview' }),
  )
  expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  expect(accept).not.toHaveBeenCalled()
})

it('locks file selection and double submission until saving completes', async () => {
  let done!: (saved: boolean) => void
  const accept = vi.fn().mockReturnValue(
    new Promise<boolean>((resolve) => {
      done = resolve
    }),
  )
  render(<MissionImport busy={false} hasMission onImport={accept} />)
  await choose()
  await screen.findByRole('heading', { name: mission.mission.title })
  await userEvent.click(screen.getByRole('checkbox'))
  const button = screen.getByRole('button', { name: 'Save imported mission' })
  fireEvent.click(button)
  fireEvent.click(button)
  expect(accept).toHaveBeenCalledTimes(1)
  expect(screen.getByLabelText('Mission JSON file')).toBeDisabled()
  await act(async () => done(false))
  await screen.findByRole('alert')
  expect(screen.getByRole('heading')).toBeInTheDocument()
})

it('does not allow import during other pending work', () => {
  render(<MissionImport busy hasMission={false} onImport={vi.fn()} />)
  expect(screen.getByLabelText('Mission JSON file')).toBeDisabled()
})

it('shows a local loader and makes no change before file reading finishes', async () => {
  let done!: (text: string) => void
  const chosen = file()
  vi.mocked(chosen.text).mockReturnValue(
    new Promise<string>((resolve) => {
      done = resolve
    }),
  )
  const accept = vi.fn()
  render(<MissionImport busy={false} hasMission={false} onImport={accept} />)
  await choose(chosen)
  expect(screen.getByText('Opening the file locally…')).toBeInTheDocument()
  expect(screen.getByLabelText('Mission JSON file')).toBeDisabled()
  expect(accept).not.toHaveBeenCalled()
  await act(async () => done(JSON.stringify(mission)))
  await screen.findByRole('heading', { name: mission.mission.title })
})

it('catches unexpected save errors without claiming success', async () => {
  render(
    <MissionImport
      busy={false}
      hasMission
      onImport={vi.fn().mockRejectedValue(new Error('private-sentinel'))}
    />,
  )
  await choose()
  await screen.findByRole('heading', { name: mission.mission.title })
  await userEvent.click(screen.getByRole('checkbox'))
  await userEvent.click(
    screen.getByRole('button', { name: 'Save imported mission' }),
  )
  await screen.findByRole('alert')
  expect(screen.queryByText(/private-sentinel/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Imported and saved/)).not.toBeInTheDocument()
})

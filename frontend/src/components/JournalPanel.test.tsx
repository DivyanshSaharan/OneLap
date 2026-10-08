import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { mission } from '../test/fixtures'
import { journalStatus, outing, owner } from '../journal/test-fixtures'
import type { useFollowUp } from '../journal/useFollowUp'
import type { useJournal } from '../journal/useJournal'
import { JournalPanel } from './JournalPanel'

function state(
  overrides: Partial<ReturnType<typeof useJournal>> = {},
): ReturnType<typeof useJournal> {
  return {
    records: [],
    cloud: [],
    nextAfter: null,
    status: null,
    restoring: false,
    busy: false,
    error: null,
    message: null,
    storageError: null,
    refresh: vi.fn().mockResolvedValue(undefined),
    check: vi.fn().mockResolvedValue(true),
    capture: vi.fn().mockResolvedValue(true),
    sync: vi.fn().mockResolvedValue(true),
    readCloud: vi.fn().mockResolvedValue(true),
    remove: vi.fn().mockResolvedValue(true),
    removeCloud: vi.fn().mockResolvedValue(true),
    ...overrides,
  }
}
const props = {
  mission,
  followUp: {
    status: null,
    suggestion: null,
    busy: false,
    error: null,
    message: null,
    check: vi.fn().mockResolvedValue(true),
    generate: vi.fn().mockResolvedValue(true),
    clear: vi.fn(),
    accepted: vi.fn(),
  } as unknown as ReturnType<typeof useFollowUp>,
  onAccept: vi.fn().mockResolvedValue(true),
  busy: false,
  connected: false,
  online: false,
  returning: 0,
}
it('records locally while offline and does not ask for cloud consent', async () => {
  const journal = state()
  render(<JournalPanel {...props} journal={journal} />)
  fireEvent.click(screen.getByText('Record an observation'))
  await userEvent.type(
    screen.getByLabelText('What did you notice?'),
    'A soft shadow.',
  )
  await userEvent.click(
    screen.getByRole('button', { name: 'Save observation on this device' }),
  )
  expect(journal.capture).toHaveBeenCalledExactlyOnceWith(mission, {
    outcome: 'completed',
    observation: 'A soft shadow.',
    feedback: null,
  })
  expect(journal.sync).not.toHaveBeenCalled()
  expect(screen.getByLabelText('What did you notice?')).toHaveValue('')
})
it('preserves typed text when local save fails', async () => {
  const journal = state({ capture: vi.fn().mockResolvedValue(false) })
  render(<JournalPanel {...props} journal={journal} />)
  fireEvent.click(screen.getByText('Record an observation'))
  await userEvent.type(
    screen.getByLabelText('What did you notice?'),
    'Keep this note.',
  )
  await userEvent.click(
    screen.getByRole('button', { name: 'Save observation on this device' }),
  )
  expect(screen.getByLabelText('What did you notice?')).toHaveValue(
    'Keep this note.',
  )
})
it('pins a typed draft to its original mission even if another mission replaces it', async () => {
  const journal = state()
  const view = render(<JournalPanel {...props} journal={journal} />)
  fireEvent.click(screen.getByText('Record an observation'))
  await userEvent.type(
    screen.getByLabelText('What did you notice?'),
    'For the earlier outing.',
  )
  view.rerender(
    <JournalPanel
      {...props}
      mission={{
        ...mission,
        id: owner,
        mission: { ...mission.mission, title: 'A different mission' },
      }}
      journal={journal}
    />,
  )
  await userEvent.click(
    screen.getByRole('button', { name: 'Save observation on this device' }),
  )
  expect(journal.capture).toHaveBeenCalledExactlyOnceWith(mission, {
    outcome: 'completed',
    observation: 'For the earlier outing.',
    feedback: null,
  })
})
it('requires explicit consent and only submits IDs present at consent time', async () => {
  const journal = state({
    status: journalStatus,
    records: [
      {
        version: 1,
        kind: 'entry',
        id: outing.id,
        owner_id: null,
        stage: 'pending',
        entry: outing,
      },
    ],
  })
  render(<JournalPanel {...props} connected online journal={journal} />)
  expect(
    screen.getByRole('button', { name: 'Sync pending changes' }),
  ).toBeDisabled()
  await userEvent.click(screen.getByRole('checkbox', { name: /For this sync/ }))
  await userEvent.click(
    screen.getByRole('button', { name: 'Sync pending changes' }),
  )
  expect(journal.sync).toHaveBeenCalledExactlyOnceWith([outing.id])
  expect(
    screen.getByRole('checkbox', { name: /For this sync/ }),
  ).not.toBeChecked()
})
it('requires confirmation before removing an observation', async () => {
  const journal = state({
    records: [
      {
        version: 1,
        kind: 'entry',
        id: outing.id,
        owner_id: null,
        stage: 'pending',
        entry: outing,
      },
    ],
  })
  render(<JournalPanel {...props} journal={journal} />)
  await userEvent.click(
    screen.getByRole('button', { name: 'Remove observation' }),
  )
  expect(journal.remove).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Confirm removal' }))
  expect(journal.remove).toHaveBeenCalledExactlyOnceWith(outing.id)
})
it('returning from pocket mode opens the form and focuses observation entry', async () => {
  render(<JournalPanel {...props} returning={1} journal={state()} />)
  await waitFor(() =>
    expect(screen.getByLabelText('What did you notice?')).toHaveFocus(),
  )
})

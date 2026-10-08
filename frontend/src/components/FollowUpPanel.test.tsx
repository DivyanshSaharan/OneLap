import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import type { useFollowUp } from '../journal/useFollowUp'
import { outing, owner } from '../journal/test-fixtures'
import { FollowUpPanel } from './FollowUpPanel'

function followUpState() {
  return {
    status: {
      enabled: true,
      disabled_reason: null,
      data_boundary: 'Only selected notes are sent to Qwen.',
    },
    suggestion: null,
    busy: false,
    error: null,
    message: null,
    check: vi.fn().mockResolvedValue(true),
    generate: vi.fn().mockResolvedValue(true),
    clear: vi.fn(),
    accepted: vi.fn(),
  } as unknown as ReturnType<typeof useFollowUp>
}

it('requires per-request consent and sends only selected earlier note IDs', async () => {
  const followUp = followUpState()
  const earlier = {
    ...outing,
    id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    recorded_at: '2026-10-05T14:00:00.000Z',
    observation: 'A different surface felt smoother.',
  }
  const later = {
    ...outing,
    id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    recorded_at: '2026-10-07T14:00:00.000Z',
    observation: 'A later note is not earlier context.',
  }
  render(
    <FollowUpPanel
      followUp={followUp}
      entries={[earlier, outing, later]}
      owner={owner}
      busy={false}
      connected
      online
      onAccept={vi.fn().mockResolvedValue(true)}
    />,
  )

  await userEvent.selectOptions(
    screen.getByLabelText('Observation to reflect on'),
    outing.id,
  )
  await userEvent.click(
    screen.getByRole('checkbox', { name: /A different surface felt smoother/ }),
  )
  expect(screen.getByText(outing.observation)).toBeInTheDocument()
  expect(screen.getByText(earlier.observation)).toBeInTheDocument()
  expect(screen.queryByText(later.observation)).not.toBeInTheDocument()
  const create = screen.getByRole('button', {
    name: 'Reflect and suggest a mission',
  })
  expect(create).toBeDisabled()
  await userEvent.click(
    screen.getByRole('checkbox', {
      name: /I approve sending this selected history/,
    }),
  )
  expect(create).toBeEnabled()
  await userEvent.click(create)
  expect(followUp.generate).toHaveBeenCalledExactlyOnceWith(owner, outing.id, [
    earlier.id,
  ])
})

it('allows an explicit status check without selecting an observation', async () => {
  const followUp = followUpState()
  render(
    <FollowUpPanel
      followUp={followUp}
      entries={[]}
      owner={owner}
      busy={false}
      connected
      online
      onAccept={vi.fn().mockResolvedValue(true)}
    />,
  )
  await userEvent.click(
    screen.getByRole('button', { name: 'Check follow-up availability' }),
  )
  expect(followUp.check).toHaveBeenCalledOnce()
})

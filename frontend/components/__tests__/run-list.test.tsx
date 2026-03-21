import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RunList } from '@/components/run-list'
import { deleteRunResult } from '@/lib/api'
import { useDemoAccess } from '@/components/demo-access-provider'
import { useRuns } from '@/components/runs-provider'
import { useScenarioCatalog } from '@/hooks/use-scenario-catalog'

const push = jest.fn()

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
  usePathname: () => '/runs/run-1/world',
}))

jest.mock('@/lib/api', () => ({
  deleteRunResult: jest.fn(),
}))

jest.mock('@/components/demo-access-provider', () => ({
  useDemoAccess: jest.fn(),
}))

jest.mock('@/components/runs-provider', () => ({
  useRuns: jest.fn(),
}))

jest.mock('@/hooks/use-scenario-catalog', () => ({
  useScenarioCatalog: jest.fn(),
}))

describe('RunList', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    window.confirm = jest.fn(() => true)
    ;(useRuns as jest.Mock).mockReturnValue({
      refreshRuns: jest.fn().mockResolvedValue(undefined),
    })
    ;(useDemoAccess as jest.Mock).mockReturnValue({
      ready: true,
      writeProtected: false,
      adminAuthorized: false,
      unlock: jest.fn(),
      lock: jest.fn(),
      refreshAccess: jest.fn(),
    })
    ;(useScenarioCatalog as jest.Mock).mockReturnValue({
      scenarioNameMap: {},
    })
  })

  it('navigates away before refreshing when deleting the active run card', async () => {
    ;(deleteRunResult as jest.Mock).mockResolvedValue({
      data: { run_id: 'run-1', status: 'deleted' },
      error: null,
      errorCode: null,
      errorDetail: null,
      status: 200,
    })
    const refreshRuns = jest.fn().mockResolvedValue(undefined)
    ;(useRuns as jest.Mock).mockReturnValue({ refreshRuns })

    render(
      <RunList
        runs={[
          { id: 'run-1', name: 'World One', status: 'paused', current_tick: 3 },
        ]}
      />
    )

    fireEvent.click(screen.getByTitle('删除'))

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith('/')
    })
    expect(refreshRuns).toHaveBeenCalled()
  })
})

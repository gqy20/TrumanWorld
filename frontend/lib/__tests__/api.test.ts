import {
  getRunResult,
  fetchApiResult,
  getTimelineResult,
  createRunResult,
  startRunResult,
  pauseRunResult,
  resumeRunResult,
  injectDirectorEventResult,
  deleteRunResult,
  restoreAllRunsResult,
  type RunSummary,
  type TimelineEvent,
} from '@/lib/api'

// Mock fetch
global.fetch = jest.fn()

const mockFetch = global.fetch as jest.MockedFunction<typeof fetch>

describe('API', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('getRunResult', () => {
    it('returns data and status on success', async () => {
      const mockRun: RunSummary = { id: '1', name: 'Test', status: 'running' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRun,
      } as Response)

      const result = await getRunResult('1')
      expect(result).toEqual({
        data: mockRun,
        error: null,
        status: 200,
      })
    })

    it('returns not_found on 404', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response)

      const result = await getRunResult('missing')
      expect(result).toEqual({
        data: null,
        error: 'not_found',
        status: 404,
      })
    })

    it('returns network_error on fetch failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      const result = await getRunResult('1')
      expect(result).toEqual({
        data: null,
        error: 'network_error',
        status: null,
      })
    })
  })

  describe('fetchApiResult', () => {
    it('returns request_failed on non-404 error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response)

      const result = await fetchApiResult<RunSummary[]>('/api/runs')
      expect(result).toEqual({
        data: null,
        error: 'request_failed',
        status: 500,
      })
    })
  })

  describe('getTimelineResult', () => {
    it('returns timeline payload on success', async () => {
      const mockTimeline = {
        run_id: '1',
        events: [
          { id: 'e1', tick_no: 1, event_type: 'talk', payload: {} },
        ] as TimelineEvent[],
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTimeline,
      } as Response)

      const result = await getTimelineResult('1')
      expect(result).toEqual({
        data: mockTimeline,
        error: null,
        status: 200,
      })
    })

    it('returns request_failed on error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response)

      const result = await getTimelineResult('1')
      expect(result).toEqual({
        data: null,
        error: 'request_failed',
        status: 500,
      })
    })
  })

  describe('createRunResult', () => {
    it('posts with correct body and returns result payload', async () => {
      const mockResponse = { id: '1', name: 'Test', status: 'created', scenario_type: 'open_world' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as Response)

      const result = await createRunResult('Test', 'open_world', true, 10)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs'),
        expect.objectContaining({
          method: 'POST',
        })
      )
      const [, requestInit] = mockFetch.mock.calls[0]
      expect(JSON.parse(requestInit?.body as string)).toEqual({
        name: 'Test',
        scenario_type: 'open_world',
        seed_demo: true,
        tick_minutes: 10,
      })
      expect(result).toEqual({
        data: mockResponse,
        error: null,
        status: 200,
      })
    })

    it('returns detailed error metadata', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response)

      const result = await createRunResult('Test')
      expect(result).toEqual({
        data: null,
        error: 'request_failed',
        status: 500,
      })
    })

    it('omits scenario_type when caller does not provide one', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: '1', name: 'Test', status: 'created', scenario_type: 'narrative_world' }),
      } as Response)

      await createRunResult('Test')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs'),
        expect.objectContaining({
          method: 'POST',
        })
      )
      const [, requestInit] = mockFetch.mock.calls[0]
      expect(JSON.parse(requestInit?.body as string)).toEqual({
        name: 'Test',
        seed_demo: true,
        tick_minutes: 5,
      })
    })
  })

  describe('startRunResult', () => {
    it('calls correct endpoint and returns detailed start response', async () => {
      const mockRun: RunSummary = { id: '1', name: 'Test', status: 'running' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRun,
      } as Response)

      const result = await startRunResult('1')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs/1/start'),
        expect.objectContaining({ method: 'POST' })
      )
      expect(result).toEqual({
        data: mockRun,
        error: null,
        status: 200,
      })
    })
  })

  describe('pauseRunResult', () => {
    it('calls correct endpoint', async () => {
      const mockRun: RunSummary = { id: '1', name: 'Test', status: 'paused' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRun,
      } as Response)

      const result = await pauseRunResult('1')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs/1/pause'),
        expect.objectContaining({ method: 'POST' })
      )
      expect(result).toEqual({
        data: mockRun,
        error: null,
        status: 200,
      })
    })
  })

  describe('resumeRunResult', () => {
    it('calls correct endpoint', async () => {
      const mockRun: RunSummary = { id: '1', name: 'Test', status: 'running' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRun,
      } as Response)

      const result = await resumeRunResult('1')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs/1/resume'),
        expect.objectContaining({ method: 'POST' })
      )
      expect(result).toEqual({
        data: mockRun,
        error: null,
        status: 200,
      })
    })
  })

  describe('injectDirectorEventResult', () => {
    it('posts with event data', async () => {
      const mockResponse = { run_id: '1', status: 'ok' }
      const eventData = {
        event_type: 'announcement',
        payload: { message: 'Hello' },
        importance: 5,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as Response)

      const result = await injectDirectorEventResult('1', eventData)

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs/1/director/events'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(eventData),
        })
      )
      expect(result).toEqual({
        data: mockResponse,
        error: null,
        status: 200,
      })
    })

    it('returns request_failed when post is rejected by server', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
      } as Response)

      const result = await injectDirectorEventResult('1', {
        event_type: 'broadcast',
        payload: { message: 'Hello' },
      })

      expect(result).toEqual({
        data: null,
        error: 'request_failed',
        status: 422,
      })
    })
  })

  describe('deleteRunResult', () => {
    it('returns success payload on delete', async () => {
      const mockResponse = { run_id: '1', status: 'deleted' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as Response)

      const result = await deleteRunResult('1')
      expect(result).toEqual({
        data: mockResponse,
        error: null,
        status: 200,
      })
    })
  })

  describe('restoreAllRunsResult', () => {
    it('returns restored runs payload', async () => {
      const mockRuns: RunSummary[] = [{ id: '1', name: 'Run 1', status: 'running' }]
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRuns,
      } as Response)

      const result = await restoreAllRunsResult()
      expect(result).toEqual({
        data: mockRuns,
        error: null,
        status: 200,
      })
    })
  })
})

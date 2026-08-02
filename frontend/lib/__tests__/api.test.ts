import {
  getRunResult,
  fetchApiResult,
  getTimelineResult,
  getAgentResult,
  createRunResult,
  startRunResult,
  pauseRunResult,
  resumeRunResult,
  injectDirectorEventResult,
  getDirectorGovernanceRecordsResult,
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

  afterEach(() => {
    jest.restoreAllMocks()
  })

  describe('getRunResult', () => {
    it('returns data and status on success', async () => {
      const mockRun: RunSummary = { id: '1', name: 'Test', status: 'running' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRun,
      } as unknown as Response)

      const result = await getRunResult('1')
      expect(result).toEqual({
        data: mockRun,
        error: null,
        errorCode: null,
        errorDetail: null,
        status: 200,
      })
    })

    it('returns not_found on 404', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        headers: {
          get: () => 'application/json',
        },
        json: async () => ({ detail: 'Run not found', code: 'RUN_NOT_FOUND' }),
      } as unknown as Response)

      const result = await getRunResult('missing')
      expect(result).toEqual({
        data: null,
        error: 'not_found',
        errorCode: 'RUN_NOT_FOUND',
        errorDetail: 'Run not found',
        status: 404,
      })
    })

    it('returns the backend request id for log correlation', async () => {
      const mockRun: RunSummary = { id: '1', name: 'Test', status: 'running' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: {
          get: (name: string) => name === 'x-request-id' ? 'req-12345678' : null,
        },
        json: async () => mockRun,
      } as unknown as Response)

      const result = await getRunResult('1')

      expect(result.requestId).toBe('req-12345678')
    })

    it('returns network_error on fetch failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => undefined)
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      const result = await getRunResult('1')
      expect(result).toEqual({
        data: null,
        error: 'network_error',
        errorCode: null,
        errorDetail: null,
        status: null,
      })
      expect(consoleSpy).toHaveBeenCalledWith(expect.objectContaining({
        event: 'api_network_error',
        method: 'GET',
        path: '/api/runs/1',
      }))
    })

    it('does not report Next.js dynamic-render control flow as an application error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => undefined)
      mockFetch.mockRejectedValueOnce(new Error('Dynamic server usage: route is dynamic'))

      const result = await getRunResult('1')

      expect(result.error).toBe('network_error')
      expect(consoleSpy).not.toHaveBeenCalled()
    })
  })

  describe('fetchApiResult', () => {
    it('returns request_failed on non-404 error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => undefined)
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        headers: {
          get: () => 'application/json',
        },
        json: async () => ({ detail: 'Boom', code: 'INTERNAL_SERVER_ERROR' }),
      } as unknown as Response)

      const result = await fetchApiResult<RunSummary[]>('/api/runs')
      expect(result).toEqual({
        data: null,
        error: 'request_failed',
        errorCode: 'INTERNAL_SERVER_ERROR',
        errorDetail: 'Boom',
        status: 500,
      })
      expect(consoleSpy).toHaveBeenCalledWith(expect.objectContaining({
        event: 'api_request_failed',
        method: 'GET',
        path: '/api/runs',
        status: 500,
      }))
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
      } as unknown as Response)

      const result = await getTimelineResult('1')
      expect(result).toEqual({
        data: mockTimeline,
        error: null,
        errorCode: null,
        errorDetail: null,
        status: 200,
      })
    })

    it('returns validation_error on 422 with validation details', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        headers: {
          get: () => 'application/json',
        },
        json: async () => ({
          detail: [{ msg: 'Field required' }],
        }),
      } as unknown as Response)

      const result = await getTimelineResult('1')
      expect(result).toEqual({
        data: null,
        error: 'validation_error',
        errorCode: null,
        errorDetail: 'Field required',
        status: 422,
      })
    })
  })

  describe('getAgentResult', () => {
    it('includes agent detail filter params in request url', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          run_id: 'run-1',
          agent_id: 'agent-1',
          name: 'Alice',
          recent_events: [],
          memories: [],
          relationships: [],
        }),
      } as unknown as Response)

      await getAgentResult('run-1', 'agent-1', {
        event_type: 'speech',
        event_query: 'secret',
        include_routine_events: false,
        event_limit: 5,
        memory_type: 'reflection',
        memory_category: 'long_term',
        memory_query: 'bob',
        min_memory_importance: 0.8,
        related_agent_id: 'bob',
        memory_limit: 3,
      })

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs/run-1/agents/agent-1?'),
        expect.objectContaining({
          cache: 'no-store',
        })
      )
      const [url] = mockFetch.mock.calls[0]
      expect(String(url)).toContain('event_type=speech')
      expect(String(url)).toContain('event_query=secret')
      expect(String(url)).toContain('include_routine_events=false')
      expect(String(url)).toContain('event_limit=5')
      expect(String(url)).toContain('memory_type=reflection')
      expect(String(url)).toContain('memory_category=long_term')
      expect(String(url)).toContain('memory_query=bob')
      expect(String(url)).toContain('min_memory_importance=0.8')
      expect(String(url)).toContain('related_agent_id=bob')
      expect(String(url)).toContain('memory_limit=3')
    })
  })

  describe('getDirectorGovernanceRecordsResult', () => {
    it('includes governance filter params in request url', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          run_id: 'run-1',
          records: [],
          total: 0,
        }),
      } as unknown as Response)

      await getDirectorGovernanceRecordsResult('run-1', {
        limit: 20,
        decision: 'warn',
        agent_id: 'agent-1',
      })

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs/run-1/director/governance-records?'),
        expect.objectContaining({
          cache: 'no-store',
        }),
      )

      const requestUrl = mockFetch.mock.calls.at(-1)?.[0] as string
      expect(requestUrl).toContain('limit=20')
      expect(requestUrl).toContain('decision=warn')
      expect(requestUrl).toContain('agent_id=agent-1')
    })
  })

  describe('createRunResult', () => {
    it('posts with correct body and returns result payload', async () => {
      const mockResponse = { id: '1', name: 'Test', status: 'created', scenario_type: 'open_world' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as unknown as Response)

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
        errorCode: null,
        errorDetail: null,
        status: 200,
      })
    })

    it('returns detailed error metadata', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => undefined)
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        headers: {
          get: () => 'application/json',
        },
        json: async () => ({ detail: 'Failed to create', code: 'INTERNAL_SERVER_ERROR' }),
      } as unknown as Response)

      const result = await createRunResult('Test')
      expect(result).toEqual({
        data: null,
        error: 'request_failed',
        errorCode: 'INTERNAL_SERVER_ERROR',
        errorDetail: 'Failed to create',
        status: 500,
      })
      expect(consoleSpy).toHaveBeenCalledWith(expect.objectContaining({
        event: 'api_request_failed',
        method: 'POST',
        path: '/api/runs',
        status: 500,
      }))
    })

    it('omits scenario_type when caller does not provide one', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: '1', name: 'Test', status: 'created', scenario_type: 'narrative_world' }),
      } as unknown as Response)

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

  describe.each([
    ['start', startRunResult, 'running'],
    ['pause', pauseRunResult, 'paused'],
    ['resume', resumeRunResult, 'running'],
  ] as const)('%sRunResult', (action, request, status) => {
    it(`posts to the ${action} endpoint and returns the run`, async () => {
      const mockRun: RunSummary = { id: '1', name: 'Test', status }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRun,
      } as unknown as Response)

      const result = await request('1')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining(`/runs/1/${action}`),
        expect.objectContaining({ method: 'POST' })
      )
      expect(result).toEqual({
        data: mockRun,
        error: null,
        errorCode: null,
        errorDetail: null,
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
        importance: 0.5,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as unknown as Response)

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
        errorCode: null,
        errorDetail: null,
        status: 200,
      })
    })

    it('returns validation_error when post is rejected by server', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        headers: {
          get: () => 'application/json',
        },
        json: async () => ({ detail: 'Invalid location', code: 'DIRECTOR_EVENT_INVALID' }),
      } as unknown as Response)

      const result = await injectDirectorEventResult('1', {
        event_type: 'broadcast',
        payload: { message: 'Hello' },
      })

      expect(result).toEqual({
        data: null,
        error: 'validation_error',
        errorCode: 'DIRECTOR_EVENT_INVALID',
        errorDetail: 'Invalid location',
        status: 422,
      })
    })
  })

  describe('deleteRunResult', () => {
    it('sends a bodyless delete and returns the success payload', async () => {
      const mockResponse = { run_id: '1', status: 'deleted' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      } as unknown as Response)

      const result = await deleteRunResult('1')
      expect(result).toEqual({
        data: mockResponse,
        error: null,
        errorCode: null,
        errorDetail: null,
        status: 200,
      })
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/runs/1'),
        expect.objectContaining({
          method: 'DELETE',
          body: undefined,
        }),
      )
    })
  })

  describe('restoreAllRunsResult', () => {
    it('returns restored runs payload', async () => {
      const mockRuns: RunSummary[] = [{ id: '1', name: 'Run 1', status: 'running' }]
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockRuns,
      } as unknown as Response)

      const result = await restoreAllRunsResult()
      expect(result).toEqual({
        data: mockRuns,
        error: null,
        errorCode: null,
        errorDetail: null,
        status: 200,
      })
    })
  })
})

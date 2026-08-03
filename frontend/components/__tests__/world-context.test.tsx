import { act, render } from "@testing-library/react";

import { WorldProvider } from "@/components/world-context";
import { makeWorldSnapshot } from "@/test-utils/app/fixtures";

const mockWorldMutate = jest.fn();
const mockPulseMutate = jest.fn();
const mockUseWorldEventStream = jest.fn();
const mockUseSWR = jest.fn((...args: unknown[]) => {
  const key = args[0];
  return {
    data: undefined,
    isValidating: false,
    mutate: typeof key === "string" && key.endsWith("/world/pulse")
      ? mockPulseMutate
      : mockWorldMutate,
  };
});

jest.mock("swr", () => ({
  __esModule: true,
  default: (...args: unknown[]) => mockUseSWR(...args),
}));

jest.mock("@/lib/ui-url-state", () => ({
  useUiSearchParams: () => ({ searchParams: new URLSearchParams() }),
}));

jest.mock("@/components/use-world-event-stream", () => {
  const actual = jest.requireActual("@/components/use-world-event-stream");
  return {
    ...actual,
    useWorldEventStream: (...args: unknown[]) => mockUseWorldEventStream(args[0]),
  };
});

describe("WorldProvider polling", () => {
  beforeEach(() => {
    mockUseSWR.mockClear();
    mockWorldMutate.mockClear();
    mockPulseMutate.mockClear();
    mockUseWorldEventStream.mockClear();
  });

  it("keeps polling after a transient error when the last good run was running", () => {
    render(
      <WorldProvider
        runId="run-1"
        initialData={makeWorldSnapshot({
          run: makeWorldSnapshot().run,
        })}
      >
        <div>world</div>
      </WorldProvider>,
    );

    const worldCall = mockUseSWR.mock.calls.find(
      (call) => typeof call[0] === "string" && call[0].endsWith("/runs/run-1/world"),
    );
    const pulseCall = mockUseSWR.mock.calls.find(
      (call) => call[0] === "/runs/run-1/world/pulse",
    );
    expect(worldCall).toBeDefined();
    expect(pulseCall).toBeDefined();

    const failedSnapshot = { data: null, error: "network_error" };
    const worldConfig = worldCall?.[2] as
      | { refreshInterval: (snapshot: typeof failedSnapshot) => number }
      | undefined;
    const pulseConfig = pulseCall?.[2] as
      | { refreshInterval: (snapshot: typeof failedSnapshot) => number }
      | undefined;
    if (!worldConfig || !pulseConfig) {
      throw new Error("Expected polling configuration");
    }
    expect(worldConfig.refreshInterval(failedSnapshot)).toBe(15000);
    expect(pulseConfig.refreshInterval(failedSnapshot)).toBe(5000);
    expect(worldConfig).toHaveProperty("revalidateOnMount", false);
    expect(worldConfig).not.toHaveProperty("compare");
  });

  it("refreshes the snapshot and pulse after any streamed world event", () => {
    jest.useFakeTimers();
    render(
      <WorldProvider runId="run-1" initialData={makeWorldSnapshot()}>
        <div>world</div>
      </WorldProvider>,
    );
    const options = mockUseWorldEventStream.mock.calls.at(-1)?.[0] as {
      onEvent: (event: { id: string; tick_no: number; event_type: string; payload: object }) => void;
    };

    act(() => {
      options.onEvent({
        id: "activity-3",
        tick_no: 3,
        event_type: "activity_step_started",
        payload: { activity_id: "activity-1" },
      });
      jest.advanceTimersByTime(120);
    });

    expect(mockWorldMutate).toHaveBeenCalled();
    expect(mockPulseMutate).toHaveBeenCalled();
    jest.useRealTimers();
  });
});

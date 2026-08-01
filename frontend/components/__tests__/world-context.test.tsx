import { render } from "@testing-library/react";

import { WorldProvider } from "@/components/world-context";
import { makeWorldSnapshot } from "@/test-utils/app/fixtures";

const mockUseSWR = jest.fn((..._args: unknown[]) => ({
  data: undefined,
  isValidating: false,
  mutate: jest.fn(),
}));

jest.mock("swr", () => ({
  __esModule: true,
  default: (...args: unknown[]) => mockUseSWR(...args),
}));

jest.mock("@/lib/ui-url-state", () => ({
  useUiSearchParams: () => ({ searchParams: new URLSearchParams() }),
}));

describe("WorldProvider polling", () => {
  beforeEach(() => {
    mockUseSWR.mockClear();
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
    expect(worldConfig).not.toHaveProperty("compare");
  });
});

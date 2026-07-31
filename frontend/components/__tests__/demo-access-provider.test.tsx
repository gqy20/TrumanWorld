import { render, screen } from "@testing-library/react";

import { DemoAccessProvider, useDemoAccess } from "@/components/demo-access-provider";
import { getDemoAccessStatusResult } from "@/lib/api";
import { errorResult } from "@/test-utils/app/render";

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    ...actual,
    getDemoAccessStatusResult: jest.fn(),
  };
});

function AccessState() {
  const { ready, writeProtected, adminAuthorized } = useDemoAccess();
  return (
    <div>
      {ready ? "ready" : "loading"}:{writeProtected ? "protected" : "open"}:
      {adminAuthorized ? "authorized" : "unauthorized"}
    </div>
  );
}

describe("DemoAccessProvider", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    jest.clearAllMocks();
  });

  it("fails closed when access status cannot be loaded", async () => {
    window.sessionStorage.setItem("trumanworld-demo-admin-password", "stale-password");
    (getDemoAccessStatusResult as jest.MockedFunction<typeof getDemoAccessStatusResult>)
      .mockResolvedValue(errorResult("network_error"));

    render(
      <DemoAccessProvider>
        <AccessState />
      </DemoAccessProvider>,
    );

    expect(await screen.findByText("ready:protected:unauthorized")).toBeInTheDocument();
  });
});

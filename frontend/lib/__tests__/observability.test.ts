import { reportApplicationError } from "@/lib/observability";

describe("frontend observability", () => {
  it("emits structured errors while redacting credentials", () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);

    reportApplicationError(new Error("Bearer unsafe-token"), {
      event: "test_error",
      apiKey: "sk-unsafe-value",
      requestId: "req-12345678",
    });

    expect(consoleSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        schemaVersion: 1,
        service: "trumanworld-frontend",
        event: "test_error",
        apiKey: "[REDACTED]",
        requestId: "req-12345678",
        error: expect.objectContaining({
          name: "Error",
          message: "[REDACTED]",
        }),
      }),
    );

    consoleSpy.mockRestore();
  });
});

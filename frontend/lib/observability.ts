type ErrorContext = Record<string, boolean | number | string | null | undefined>;

const REDACTED = "[REDACTED]";
const SENSITIVE_KEY = /api[_-]?key|authorization|cookie|password|secret|token/i;
const SENSITIVE_VALUE_PATTERNS = [
  /bearer\s+[A-Za-z0-9._~+/-]+=*/gi,
  /\b(?:sk|gsk|xai)-[A-Za-z0-9_-]{8,}\b/gi,
  /\b([a-z][a-z0-9+.-]*:\/\/[^:/\s]+:)[^@\s]+@/gi,
];

function sanitizeValue(value: string): string {
  return SENSITIVE_VALUE_PATTERNS.reduce(
    (sanitized, pattern) => sanitized.replace(pattern, REDACTED),
    value,
  );
}

function sanitizeContext(context: ErrorContext): ErrorContext {
  return Object.fromEntries(
    Object.entries(context).map(([key, value]) => [
      key,
      SENSITIVE_KEY.test(key)
        ? REDACTED
        : typeof value === "string"
          ? sanitizeValue(value)
          : value,
    ]),
  );
}

export function reportApplicationError(error: unknown, context: ErrorContext = {}): void {
  const normalizedError =
    error instanceof Error
      ? { name: error.name, message: sanitizeValue(error.message) }
      : { name: "UnknownError", message: sanitizeValue(String(error)) };

  console.error({
    schemaVersion: 1,
    service: "trumanworld-frontend",
    level: "ERROR",
    event: "frontend_error",
    ...sanitizeContext(context),
    error: normalizedError,
  });
}

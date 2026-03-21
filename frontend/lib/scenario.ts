export function formatScenarioLabel(scenarioType?: string | null): string {
  if (!scenarioType) {
    return "Unknown World";
  }

  return scenarioType
    .split("_")
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

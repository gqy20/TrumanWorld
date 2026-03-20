import pricingData from "@/lib/llm-pricing.json";

export type LlmPricing = {
  displayName: string;
  input: number;
  output: number;
  cacheRead: number;
  cacheCreation: number;
};

type RawPricing = {
  display_name?: string;
  input: number;
  output: number;
  cache_read: number;
  cache_creation: number;
};

function normalizeModelName(model: string) {
  return model.trim().toLowerCase();
}

export function getLlmPricing(modelName: string | null | undefined): LlmPricing | null {
  if (!modelName) return null;
  const normalized = normalizeModelName(modelName);
  const raw = (pricingData.models as Record<string, RawPricing>)[normalized];
  if (!raw) return null;
  return {
    displayName: raw.display_name ?? modelName,
    input: raw.input,
    output: raw.output,
    cacheRead: raw.cache_read,
    cacheCreation: raw.cache_creation,
  };
}

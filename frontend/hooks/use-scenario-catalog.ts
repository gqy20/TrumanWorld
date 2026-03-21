"use client";

import { useEffect, useMemo, useState } from "react";

import { listScenariosResult } from "@/lib/api";
import type { ScenarioSummary } from "@/lib/types";

export function useScenarioCatalog() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const result = await listScenariosResult();
      if (cancelled || !result.data) {
        return;
      }
      setScenarios(result.data);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const scenarioNameMap = useMemo(
    () => Object.fromEntries(scenarios.map((scenario) => [scenario.id, scenario.name])),
    [scenarios]
  );

  return { scenarios, scenarioNameMap };
}

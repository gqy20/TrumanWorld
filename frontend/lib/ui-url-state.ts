"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const UI_URL_STATE_CHANGE = "ui-url-state-change";

function getCurrentSearch() {
  if (typeof window === "undefined") {
    return "";
  }
  return window.location.search;
}

export function useUiSearchParams() {
  const [search, setSearch] = useState(getCurrentSearch);

  useEffect(() => {
    const sync = () => setSearch(getCurrentSearch());
    window.addEventListener("popstate", sync);
    window.addEventListener(UI_URL_STATE_CHANGE, sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener(UI_URL_STATE_CHANGE, sync);
    };
  }, []);

  const searchParams = useMemo(() => new URLSearchParams(search), [search]);

  const replaceSearchParams = useCallback((updates: Record<string, string | null>) => {
    if (typeof window === "undefined") {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    for (const [key, value] of Object.entries(updates)) {
      if (value == null || value === "") {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    }

    const query = params.toString();
    const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
    window.history.replaceState(window.history.state, "", nextUrl);
    window.dispatchEvent(new Event(UI_URL_STATE_CHANGE));
  }, []);

  return { searchParams, replaceSearchParams };
}

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  clearDemoAdminPassword,
  getDemoAccessStatusResult,
  setDemoAdminPassword,
} from "@/lib/api";

type DemoAccessContextValue = {
  ready: boolean;
  writeProtected: boolean;
  adminAuthorized: boolean;
  unlock: (password: string) => Promise<{ ok: boolean; error?: string }>;
  lock: () => void;
  refreshAccess: () => Promise<void>;
};

const DemoAccessContext = createContext<DemoAccessContextValue | null>(null);

export function DemoAccessProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [writeProtected, setWriteProtected] = useState(false);
  const [adminAuthorized, setAdminAuthorized] = useState(false);

  const refreshAccess = useCallback(async () => {
    const result = await getDemoAccessStatusResult();
    if (result.data) {
      setWriteProtected(result.data.write_protected);
      setAdminAuthorized(result.data.admin_authorized);
    } else {
      setWriteProtected(true);
      setAdminAuthorized(false);
    }
    setReady(true);
  }, []);

  useEffect(() => {
    void refreshAccess();
  }, [refreshAccess]);

  const unlock = useCallback(
    async (password: string) => {
      setDemoAdminPassword(password);
      const result = await getDemoAccessStatusResult();
      if (!result.data?.admin_authorized) {
        clearDemoAdminPassword();
        setAdminAuthorized(false);
        setWriteProtected(result.data?.write_protected ?? true);
        return { ok: false, error: "密码不正确" };
      }
      setWriteProtected(result.data.write_protected);
      setAdminAuthorized(true);
      return { ok: true };
    },
    [],
  );

  const lock = useCallback(() => {
    clearDemoAdminPassword();
    setAdminAuthorized(false);
  }, []);

  const value = useMemo(
    () => ({ ready, writeProtected, adminAuthorized, unlock, lock, refreshAccess }),
    [adminAuthorized, lock, ready, refreshAccess, unlock, writeProtected],
  );

  return <DemoAccessContext.Provider value={value}>{children}</DemoAccessContext.Provider>;
}

export function useDemoAccess() {
  const value = useContext(DemoAccessContext);
  if (value == null) {
    throw new Error("useDemoAccess must be used within DemoAccessProvider");
  }
  return value;
}

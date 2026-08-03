"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useWorldEventStream } from "@/components/use-world-event-stream";
import { buildApiUrl } from "@/lib/api";
import type { WorldEvent } from "@/lib/types";

import { GodotBridge } from "./godot-bridge";
import {
  PHASE_ZERO_RUN_ID,
  PHASE_ZERO_WORLD_SNAPSHOT,
} from "./phase-zero-fixture";
import type {
  GodotEnvelope,
  GodotClientMessageType,
  GodotSelectionPayload,
  GodotWorldSnapshot,
} from "./protocol";

type BridgeStatus = "loading" | "ready" | "error";

type Props = {
  runId?: string;
  snapshot?: GodotWorldSnapshot;
  readyTimeoutMs?: number;
};

export function GodotWorldHost({
  runId,
  snapshot: providedSnapshot,
  readyTimeoutMs = 15_000,
}: Props) {
  const resolvedRunId = runId ?? PHASE_ZERO_RUN_ID;
  const isLiveRun = Boolean(runId && !providedSnapshot);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const bridgeRef = useRef<GodotBridge | null>(null);
  const snapshotRef = useRef<GodotWorldSnapshot | null>(
    providedSnapshot ?? (isLiveRun ? null : PHASE_ZERO_WORLD_SNAPSHOT),
  );
  const readyRef = useRef(false);
  const readyMapRef = useRef<{ mapId: string; contentHash: string } | null>(null);
  const refreshTimerRef = useRef<number | null>(null);
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus>("loading");
  const [protocolError, setProtocolError] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [connectionRevision, setConnectionRevision] = useState(0);
  const [liveSnapshot, setLiveSnapshot] = useState<GodotWorldSnapshot | null>(null);

  const snapshot =
    providedSnapshot ?? (isLiveRun ? liveSnapshot : PHASE_ZERO_WORLD_SNAPSHOT);

  useEffect(() => {
    snapshotRef.current = snapshot;
  }, [snapshot]);

  const selectedAgent = useMemo(
    () => snapshot?.agents.find((agent) => agent.id === selectedAgentId) ?? null,
    [selectedAgentId, snapshot],
  );

  const sendSnapshot = useCallback((nextSnapshot: GodotWorldSnapshot) => {
    if (!readyRef.current) return;
    const readyMap = readyMapRef.current;
    if (
      readyMap &&
      (readyMap.mapId !== nextSnapshot.map_id ||
        readyMap.contentHash !== nextSnapshot.map_content_hash)
    ) {
      setProtocolError("map_mismatch");
      setBridgeStatus("error");
      return;
    }
    bridgeRef.current?.post("initialize", {
      client: "next-director-console",
      map_id: nextSnapshot.map_id,
    });
    bridgeRef.current?.post(
      "world_snapshot",
      nextSnapshot as unknown as Record<string, unknown>,
    );
    setBridgeStatus("ready");
  }, []);

  const fetchLiveSnapshot = useCallback(async () => {
    if (!isLiveRun) return;
    try {
      const response = await fetch(buildApiUrl(`/runs/${resolvedRunId}/world`), {
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) throw new Error(`snapshot_${response.status}`);
      const value = (await response.json()) as unknown;
      const nextSnapshot = decodeWorldSnapshot(value);
      if (!nextSnapshot) throw new Error("invalid_world_snapshot");
      setLiveSnapshot(nextSnapshot);
      sendSnapshot(nextSnapshot);
      setProtocolError(null);
    } catch (error) {
      setProtocolError(error instanceof Error ? error.message : "snapshot_failed");
      setBridgeStatus("error");
    }
  }, [isLiveRun, resolvedRunId, sendSnapshot]);

  const handleGodotMessage = useCallback(
    (message: GodotEnvelope<GodotClientMessageType>) => {
      if (message.type === "ready") {
        readyRef.current = true;
        readyMapRef.current = {
          mapId: String(message.payload.map_id ?? ""),
          contentHash: String(message.payload.map_content_hash ?? ""),
        };
        const currentSnapshot = snapshotRef.current;
        if (!currentSnapshot) return;
        if (
          message.payload.map_id !== currentSnapshot.map_id ||
          message.payload.map_content_hash !== currentSnapshot.map_content_hash
        ) {
          setProtocolError("map_mismatch");
          setBridgeStatus("error");
          return;
        }
        sendSnapshot(currentSnapshot);
        return;
      }
      if (message.type === "selection_changed") {
        const selection = message.payload as GodotSelectionPayload;
        if (selection.kind === "agent") setSelectedAgentId(selection.id);
      }
    },
    [sendSnapshot],
  );

  useEffect(() => {
    void fetchLiveSnapshot();
  }, [fetchLiveSnapshot]);

  const handleWorldEvent = useCallback(
    (event: WorldEvent) => {
      bridgeRef.current?.post("world_event_batch", { events: [event] });
      if (refreshTimerRef.current !== null) window.clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = window.setTimeout(() => {
        refreshTimerRef.current = null;
        void fetchLiveSnapshot();
      }, 100);
    },
    [fetchLiveSnapshot],
  );

  useWorldEventStream({
    enabled: isLiveRun && bridgeStatus === "ready",
    latestKnownTick: snapshot?.tick ?? 0,
    onEvent: handleWorldEvent,
    runId: resolvedRunId,
  });

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    setBridgeStatus("loading");
    setProtocolError(null);
    readyRef.current = false;
    readyMapRef.current = null;
    const bridge = new GodotBridge(
      iframe,
      resolvedRunId,
      window.location.origin,
      handleGodotMessage,
      (error) => setProtocolError(error),
    );
    bridge.start();
    bridgeRef.current = bridge;

    const timeout = window.setTimeout(() => {
      setBridgeStatus((current) => (current === "ready" ? current : "error"));
    }, readyTimeoutMs);

    return () => {
      window.clearTimeout(timeout);
      bridge.post("dispose", {});
      bridge.stop();
      readyRef.current = false;
      readyMapRef.current = null;
      if (refreshTimerRef.current !== null) window.clearTimeout(refreshTimerRef.current);
      if (bridgeRef.current === bridge) bridgeRef.current = null;
    };
  }, [connectionRevision, handleGodotMessage, readyTimeoutMs, resolvedRunId]);

  const focusAgent = (agentId: string) => {
    setSelectedAgentId(agentId);
    bridgeRef.current?.post("focus_entity", { kind: "agent", id: agentId });
  };

  return (
    <section className="grid min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
      <div className="relative min-h-[540px] overflow-hidden rounded-3xl border border-slate-700 bg-[#0e141d] shadow-[0_24px_80px_rgba(15,23,42,0.24)]">
        <iframe
          key={connectionRevision}
          ref={iframeRef}
          src="/godot-world/index.html"
          title="Godot 具身世界技术验证"
          className="h-full min-h-[540px] w-full border-0"
          allow="autoplay; fullscreen"
        />

        <div className="pointer-events-none absolute top-4 right-4 flex items-center gap-2 rounded-full border border-white/10 bg-slate-950/75 px-3 py-1.5 text-xs text-slate-200 backdrop-blur">
          <span
            className={`h-2 w-2 rounded-full ${
              bridgeStatus === "ready"
                ? "bg-emerald-400"
                : bridgeStatus === "error"
                  ? "bg-rose-400"
                  : "animate-pulse bg-amber-300"
            }`}
          />
          {bridgeStatus === "ready"
            ? "Bridge ready"
            : bridgeStatus === "error"
              ? "Godot unavailable"
              : "Loading Godot"}
        </div>

        {bridgeStatus === "error" ? (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0e141d]/95 p-8">
            <div className="max-w-md text-center">
              <p className="text-lg font-semibold text-white">Godot Web 构建尚未就绪</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                运行 <code className="rounded bg-white/10 px-1.5 py-0.5">make godot-export-web</code>
                后重新连接。当前正式 Voxel 世界不会受到影响。
              </p>
              <button
                type="button"
                onClick={() => setConnectionRevision((current) => current + 1)}
                className="pointer-events-auto mt-5 rounded-xl bg-emerald-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200"
              >
                重新连接
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <aside className="rounded-3xl border border-white/70 bg-white/80 p-5 shadow-sm backdrop-blur">
        <p className="text-xs font-semibold tracking-[0.18em] text-slate-500 uppercase">
          {isLiveRun ? "Live Run · Phase 3" : "Phase 3 Fixture"}
        </p>
        <h2 className="mt-2 text-xl font-semibold text-slate-900">协议与选择闭环</h2>
        <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-xl bg-slate-100 p-3">
            <dt className="text-xs text-slate-500">Map</dt>
            <dd className="mt-1 font-medium text-slate-900">{snapshot?.map_id ?? "loading"}</dd>
          </div>
          <div className="rounded-xl bg-slate-100 p-3">
            <dt className="text-xs text-slate-500">Agents</dt>
            <dd className="mt-1 font-medium text-slate-900">{snapshot?.agents.length ?? 0}</dd>
          </div>
        </dl>

        <div className="mt-5 space-y-2" aria-label="Fixture 居民">
          {(snapshot?.agents ?? []).map((agent) => (
            <button
              key={agent.id}
              type="button"
              onClick={() => focusAgent(agent.id)}
              className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left transition ${
                selectedAgentId === agent.id
                  ? "border-emerald-400 bg-emerald-50 text-emerald-950"
                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
              }`}
            >
              <span className="font-medium">{agent.name}</span>
              <span className="text-xs text-slate-500">
                {agent.activity?.activity_type ?? "idle"}
              </span>
            </button>
          ))}
        </div>

        <div className="mt-5 min-h-20 rounded-xl border border-dashed border-slate-300 p-3 text-sm text-slate-600">
          {selectedAgent ? (
            <>
              已选择 <strong className="text-slate-900">{selectedAgent.name}</strong>
              <p className="mt-1 text-xs text-slate-500">
                点击 Godot 角色或此列表，选择状态会跨 Bridge 同步。
              </p>
            </>
          ) : (
            "尚未选择居民"
          )}
        </div>

        {protocolError ? (
          <p role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-xs text-rose-700">
            协议错误：{protocolError}
          </p>
        ) : null}
      </aside>
    </section>
  );
}

function decodeWorldSnapshot(value: unknown): GodotWorldSnapshot | null {
  if (!value || typeof value !== "object") return null;
  const snapshot = value as Partial<GodotWorldSnapshot>;
  if (
    typeof snapshot.map_id !== "string" ||
    typeof snapshot.map_content_hash !== "string" ||
    typeof snapshot.tick !== "number" ||
    typeof snapshot.world_time !== "string" ||
    typeof snapshot.run_status !== "string" ||
    typeof snapshot.simulation_speed !== "number" ||
    !Array.isArray(snapshot.agents) ||
    !Array.isArray(snapshot.object_states)
  ) {
    return null;
  }
  return {
    ...snapshot,
    conversations: Array.isArray(snapshot.conversations) ? snapshot.conversations : [],
  } as GodotWorldSnapshot;
}

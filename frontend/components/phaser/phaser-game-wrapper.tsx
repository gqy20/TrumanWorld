"use client";

import { useEffect, useRef } from "react";
import * as Phaser from "phaser";

import type { SceneWorld } from "@/lib/world-scene-adapter";

import { WorldScene } from "./world-scene";

export interface PhaserGameWrapperProps {
  sceneWorld: SceneWorld;
  width?: number;
  height?: number;
  zoom?: number;
  highlightedLocationId?: string | null;
  highlightedAgentId?: string | null;
  onAgentClick?: (agentId: string) => void;
  onLocationClick?: (locationId: string) => void;
}

function isWorldScene(
  value: unknown
): value is Pick<
  WorldScene,
  "syncWorld" | "setHighlightedLocation" | "setHighlightedAgent" | "events"
> {
  return Boolean(
    value &&
      typeof value === "object" &&
      "syncWorld" in value &&
      typeof value.syncWorld === "function" &&
      "setHighlightedLocation" in value &&
      typeof value.setHighlightedLocation === "function" &&
      "setHighlightedAgent" in value &&
      typeof value.setHighlightedAgent === "function" &&
      "events" in value
  );
}

export function PhaserGameWrapper({
  sceneWorld,
  width = 800,
  height = 600,
  zoom = 1,
  highlightedLocationId,
  highlightedAgentId,
  onAgentClick,
  onLocationClick,
}: PhaserGameWrapperProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);
  const pendingSceneWorldRef = useRef<SceneWorld | null>(sceneWorld);

  useEffect(() => {
    if (!containerRef.current || gameRef.current) {
      return;
    }

    gameRef.current = new Phaser.Game({
      type: Phaser.AUTO,
      parent: containerRef.current,
      width,
      height,
      backgroundColor: "#eef5e8",
      pixelArt: true,
      render: {
        pixelArt: true,
        antialias: false,
        roundPixels: true,
      },
      zoom,
      scene: [WorldScene],
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
    });

    const attachReadyListener = window.setInterval(() => {
      const scene = gameRef.current?.scene.getScene("WorldScene");
      if (!isWorldScene(scene)) {
        return;
      }

      window.clearInterval(attachReadyListener);

      const syncPendingWorld = () => {
        if (pendingSceneWorldRef.current) {
          scene.syncWorld(pendingSceneWorldRef.current);
        }
      };

      scene.events.on("scene:ready", syncPendingWorld);
      syncPendingWorld();
    }, 50);

    return () => {
      window.clearInterval(attachReadyListener);
      if (gameRef.current) {
        gameRef.current.destroy(true);
        gameRef.current = null;
      }
    };
  }, [height, width, zoom]);

  useEffect(() => {
    pendingSceneWorldRef.current = sceneWorld;
    const scene = gameRef.current?.scene.getScene("WorldScene");
    if (!isWorldScene(scene)) {
      return;
    }
    scene.syncWorld(sceneWorld);
  }, [sceneWorld]);

  useEffect(() => {
    const scene = gameRef.current?.scene.getScene("WorldScene");
    if (!isWorldScene(scene)) {
      return;
    }
    scene.setHighlightedLocation(highlightedLocationId ?? null);
  }, [highlightedLocationId]);

  useEffect(() => {
    const scene = gameRef.current?.scene.getScene("WorldScene");
    if (!isWorldScene(scene)) {
      return;
    }
    scene.setHighlightedAgent(highlightedAgentId ?? null);
  }, [highlightedAgentId]);

  useEffect(() => {
    const scene = gameRef.current?.scene.getScene("WorldScene");
    if (!isWorldScene(scene)) {
      return;
    }

    const handleAgentClick = (agentId: string) => onAgentClick?.(agentId);
    const handleLocationClick = (locationId: string) => onLocationClick?.(locationId);

    scene.events.on("agent:click", handleAgentClick);
    scene.events.on("location:click", handleLocationClick);
    return () => {
      scene.events.off("agent:click", handleAgentClick);
      scene.events.off("location:click", handleLocationClick);
    };
  }, [onAgentClick, onLocationClick]);

  return (
    <div
      ref={containerRef}
      data-testid="phaser-game-container"
      className="relative mx-auto h-full min-h-[560px] w-full overflow-hidden rounded-2xl border border-emerald-100 bg-[#eef5e8] shadow-xs"
    />
  );
}

interface ViewToggleButtonProps {
  currentView: "svg" | "phaser";
  onToggle: (view: "svg" | "phaser") => void;
}

export function ViewToggleButton({ currentView, onToggle }: ViewToggleButtonProps) {
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/80 p-1 shadow-xs">
      <button
        type="button"
        onClick={() => onToggle("svg")}
        className={`rounded-xl px-3 py-1.5 text-sm font-medium transition ${
          currentView === "svg"
            ? "bg-slate-900 text-white"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        导演地图
      </button>
      <button
        type="button"
        onClick={() => onToggle("phaser")}
        className={`rounded-xl px-3 py-1.5 text-sm font-medium transition ${
          currentView === "phaser"
            ? "bg-emerald-600 text-white"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        舞台视图
      </button>
    </div>
  );
}

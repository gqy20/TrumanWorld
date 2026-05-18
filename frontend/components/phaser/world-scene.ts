import * as Phaser from "phaser";

import type { SceneAgent, SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";
import { getTownAssetPackManifest, preloadTownAssetPack } from "./world-asset-pack";
import {
  getAgentPosition as getAgentPositionPoint,
  mapWorldToCanvas as mapWorldToCanvasPoint,
} from "./world-scene-geometry";
import {
  focusCameraOnSelection as focusSceneCameraOnSelection,
  hideTooltip as hideSceneTooltip,
  playTapFeedback as playSceneTapFeedback,
  refreshAgentHighlights as refreshSceneAgentHighlights,
  refreshLocationHighlights as refreshSceneLocationHighlights,
  showTooltip as showSceneTooltip,
} from "./world-scene-interactions";
import {
  createStageShell as createSceneStageShell,
  syncAmbience as syncSceneAmbience,
  syncStageTheme as syncSceneStageTheme,
  syncTownGround as syncSceneTownGround,
  type StageNodes,
} from "./world-scene-stage";
import {
  refreshAgentAnimationFrames as refreshSceneAgentAnimationFrames,
  syncAgents as syncSceneAgents,
  syncBubbles as syncSceneBubbles,
  syncLocations as syncSceneLocations,
  syncMoveTrails as syncSceneMoveTrails,
  type AgentNode,
  type BubbleNode,
  type LocationNode,
  type TrailNode,
} from "./world-scene-sync";
import {
  createPixelTextures as createScenePixelTextures,
  ensureAgentTexture as ensureSceneAgentTexture,
  ensureGroundTexture as ensureSceneGroundTexture,
  ensureLocationTexture as ensureSceneLocationTexture,
} from "./world-scene-textures";

export class WorldScene extends Phaser.Scene {
  private locationNodes = new Map<string, LocationNode>();
  private agentNodes = new Map<string, AgentNode>();
  private trailNodes = new Map<string, TrailNode>();
  private bubbleNodes = new Map<string, BubbleNode>();
  private stageNodes: StageNodes | null = null;
  private currentWorld: SceneWorld | null = null;
  private highlightedLocationId: string | null = null;
  private highlightedAgentId: string | null = null;

  constructor() {
    super({ key: "WorldScene" });
  }

  preload(): void {
    preloadTownAssetPack(this);
  }

  create(_initialWorld?: SceneWorld): void {
    this.createPixelTextures();
    this.stageNodes = createSceneStageShell(this);

    this.events.emit("scene:ready");
    if (this.currentWorld) {
      this.syncWorld(this.currentWorld);
    }
  }

  update(_time: number, _delta: number): void {
    refreshSceneAgentAnimationFrames(
      this.agentNodes,
      getTownAssetPackManifest(this),
      this.time?.now ?? Date.now(),
    );
  }

  syncWorld(world: SceneWorld): void {
    this.currentWorld = world;
    if (!this.stageNodes) {
      return;
    }
    syncSceneStageTheme(this, this.stageNodes, world, (groundPreset) =>
      this.ensureGroundTexture(groundPreset)
    );
    syncSceneTownGround(this.stageNodes, world.locations);
    syncSceneAmbience(this.stageNodes, world);
    this.syncLocations(world.locations);
    this.syncAgents(world.agents, world.locations);
    this.syncMoveTrails(world);
    this.syncBubbles(world);
  }

  updateWorldData(world: SceneWorld): void {
    this.syncWorld(world);
  }

  setHighlightedLocation(locationId: string | null): void {
    this.highlightedLocationId = locationId;
    this.refreshLocationHighlights();
    this.focusCameraOnSelection();
  }

  setHighlightedAgent(agentId: string | null): void {
    this.highlightedAgentId = agentId;
    this.refreshAgentHighlights();
    this.focusCameraOnSelection();
  }

  private syncContext() {
    return {
      scene: this,
      ensureLocationTexture: (location: SceneLocation) => this.ensureLocationTexture(location),
      ensureAgentTexture: (agent: SceneAgent) => this.ensureAgentTexture(agent),
      assetPackManifest: getTownAssetPackManifest(this),
      nowMs: this.time?.now ?? Date.now(),
      mapWorldToCanvas: (x: number, y: number, locations: SceneLocation[]) =>
        this.mapWorldToCanvas(x, y, locations),
      getAgentPosition: (location: SceneLocation, slotIndex: number) =>
        this.getAgentPosition(location, slotIndex),
      playTapFeedback: (...targets: Phaser.GameObjects.GameObject[]) =>
        this.playTapFeedback(...targets),
      showTooltip: (x: number, y: number, text: string) => this.showTooltip(x, y, text),
      hideTooltip: () => this.hideTooltip(),
    };
  }

  private syncLocations(locations: SceneLocation[]): void {
    syncSceneLocations(this.syncContext(), this.locationNodes, locations);
    this.refreshLocationHighlights();
  }

  private syncAgents(agents: SceneAgent[], locations: SceneLocation[]): void {
    syncSceneAgents(this.syncContext(), this.agentNodes, agents, locations);
    this.refreshAgentHighlights();
  }

  private syncMoveTrails(world: SceneWorld): void {
    syncSceneMoveTrails(this.syncContext(), this.trailNodes, world);
  }

  private syncBubbles(world: SceneWorld): void {
    syncSceneBubbles(this.syncContext(), this.bubbleNodes, world);
  }

  private getAgentPosition(location: SceneLocation, slotIndex: number) {
    return getAgentPositionPoint(location, slotIndex, this.currentWorld?.locations ?? [location]);
  }

  private refreshLocationHighlights(): void {
    refreshSceneLocationHighlights(this.locationNodes, this.highlightedLocationId);
  }

  private refreshAgentHighlights(): void {
    refreshSceneAgentHighlights(this, this.agentNodes, this.highlightedAgentId);
  }

  private focusCameraOnSelection(): void {
    focusSceneCameraOnSelection(
      this.cameras.main,
      this.locationNodes,
      this.agentNodes,
      this.highlightedLocationId,
      this.highlightedAgentId
    );
  }

  private showTooltip(x: number, y: number, text: string): void {
    showSceneTooltip(this.stageNodes?.tooltip ?? null, x, y, text);
  }

  private hideTooltip(): void {
    hideSceneTooltip(this.stageNodes?.tooltip ?? null);
  }

  private playTapFeedback(...targets: Phaser.GameObjects.GameObject[]): void {
    playSceneTapFeedback(this, ...targets);
  }

  private mapWorldToCanvas(
    x: number,
    y: number,
    locations: SceneLocation[],
  ): { x: number; y: number } {
    return mapWorldToCanvasPoint(x, y, locations);
  }

  private createPixelTextures(): void {
    createScenePixelTextures(this);
  }

  private ensureGroundTexture(groundPreset: string): string {
    return ensureSceneGroundTexture(this, groundPreset);
  }

  private ensureLocationTexture(location: SceneLocation): void {
    ensureSceneLocationTexture(this, location);
  }

  private ensureAgentTexture(agent: SceneAgent): void {
    ensureSceneAgentTexture(this, agent);
  }

}

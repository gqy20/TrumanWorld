import * as Phaser from "phaser";

import type { SceneAgent, SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";
import {
  getAgentPosition as getAgentPositionPoint,
  mapWorldToCanvas as mapWorldToCanvasPoint,
} from "./world-scene-geometry";
import {
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  getStagePalette,
  mergeStagePalette,
  parseRgbaColor,
} from "./world-scene-style";
import {
  focusCameraOnSelection as focusSceneCameraOnSelection,
  hideTooltip as hideSceneTooltip,
  playTapFeedback as playSceneTapFeedback,
  refreshAgentHighlights as refreshSceneAgentHighlights,
  refreshLocationHighlights as refreshSceneLocationHighlights,
  showTooltip as showSceneTooltip,
  type TooltipNode,
} from "./world-scene-interactions";
import {
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
  private stageGround: Phaser.GameObjects.TileSprite | null = null;
  private stageHeader: Phaser.GameObjects.Rectangle | null = null;
  private stageVignette: Phaser.GameObjects.Ellipse | null = null;
  private ambienceOverlay: Phaser.GameObjects.Rectangle | null = null;
  private ambienceLabel: Phaser.GameObjects.Text | null = null;
  private tooltip: TooltipNode | null = null;
  private currentWorld: SceneWorld | null = null;
  private highlightedLocationId: string | null = null;
  private highlightedAgentId: string | null = null;

  constructor() {
    super({ key: "WorldScene" });
  }

  preload(): void {}

  create(_initialWorld?: SceneWorld): void {
    const palette = getStagePalette();
    this.cameras.main.setBackgroundColor(palette.backgroundColor);
    this.cameras.main.setZoom(1);
    this.createPixelTextures();

    this.stageGround = this.add
      .tileSprite(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, CANVAS_WIDTH, CANVAS_HEIGHT, "pixel-ground")
      .setDepth(-20)
      .setAlpha(0.98);

    this.stageHeader = this.add
      .rectangle(CANVAS_WIDTH / 2, 86, CANVAS_WIDTH, 132, 0x172554)
      .setDepth(-19)
      .setAlpha(0.42);

    this.stageVignette = this.add
      .ellipse(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2 + 18, 700, 470, 0x0f172a)
      .setDepth(-18)
      .setAlpha(0.16);

    this.ambienceOverlay = this.add
      .rectangle(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, CANVAS_WIDTH, CANVAS_HEIGHT, 0xffffff)
      .setDepth(-18)
      .setAlpha(0);

    this.ambienceLabel = this.add
      .text(20, 20, "World Stage", {
        color: palette.labelColor,
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "12px",
        fontStyle: "600",
      })
      .setDepth(60);

    const tooltipBox = this.add
      .rectangle(0, 0, 160, 32, 0x020617, 0.92)
      .setStrokeStyle(1, 0x334155, 0.9)
      .setDepth(90)
      .setVisible(false);
    const tooltipText = this.add
      .text(0, 0, "", {
        color: "#e2e8f0",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "11px",
      })
      .setOrigin(0.5)
      .setDepth(91)
      .setVisible(false);
    this.tooltip = { box: tooltipBox, text: tooltipText };

    this.events.emit("scene:ready");
    if (this.currentWorld) {
      this.syncWorld(this.currentWorld);
    }
  }

  syncWorld(world: SceneWorld): void {
    this.currentWorld = world;
    if (!this.ambienceOverlay) {
      return;
    }
    this.syncStageTheme(world);
    this.syncAmbience(world);
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

  private syncAmbience(world: SceneWorld): void {
    if (!this.ambienceOverlay) {
      return;
    }

    this.ambienceOverlay.setFillStyle(
      parseRgbaColor(world.ambience.overlayColor),
      world.ambience.isDark ? 0.24 : 0.1
    );
    this.ambienceLabel?.setText(`Stage / ${world.ambience.label}`);
  }

  private syncStageTheme(world: SceneWorld): void {
    const palette = mergeStagePalette(getStagePalette(world.stage.theme), world.stage.palette);
    const groundPreset = world.stage.groundPreset ?? "default";
    const textureKey = this.ensureGroundTexture(groundPreset);
    this.cameras.main.setBackgroundColor(palette.backgroundColor);
    this.stageGround?.setTexture(textureKey);
    this.stageHeader?.setFillStyle(palette.headerColor, palette.headerAlpha);
    this.stageVignette?.setFillStyle(palette.vignetteColor, palette.vignetteAlpha);
    this.ambienceLabel?.setColor(palette.labelColor);
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
    showSceneTooltip(this.tooltip, x, y, text);
  }

  private hideTooltip(): void {
    hideSceneTooltip(this.tooltip);
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

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

type TooltipNode = {
  box: Phaser.GameObjects.Rectangle;
  text: Phaser.GameObjects.Text;
};

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
    for (const [locationId, node] of this.locationNodes.entries()) {
      const isHighlighted = this.highlightedLocationId === locationId;
      if (isHighlighted) {
        node.body.setTint(0xf8fafc);
        node.body.setScale(1.06);
      } else {
        node.body.clearTint();
        node.body.setScale(1);
      }
      node.label.setScale(isHighlighted ? 1.05 : 1);
      node.badge.setScale(isHighlighted ? 1.05 : 1);
      node.glow.setAlpha(isHighlighted ? 0.34 : node.glow.alpha);
    }
  }

  private refreshAgentHighlights(): void {
    for (const [agentId, node] of this.agentNodes.entries()) {
      const isHighlighted = this.highlightedAgentId === agentId;
      node.pulseTween?.stop();
      if (isHighlighted) {
        node.body.setTint(0xfef08a);
        node.marker.setScale(1.08);
        node.label.setScale(1.08);
        node.pulseTween = this.tweens.add({
          targets: [node.body, node.marker, node.label],
          scale: { from: 1, to: 1.08 },
          duration: 700,
          yoyo: true,
          repeat: -1,
          ease: "Sine.InOut",
        });
      } else {
        node.body.clearTint();
        node.body.setScale(1);
        node.marker.setScale(1);
        node.label.setScale(1);
        node.pulseTween = undefined;
      }
    }
  }

  private focusCameraOnSelection(): void {
    const camera = this.cameras.main;
    const targetAgentNode = this.highlightedAgentId
      ? this.agentNodes.get(this.highlightedAgentId)
      : undefined;
    if (targetAgentNode) {
      camera.pan(targetAgentNode.body.x, targetAgentNode.body.y, 320, "Sine.easeInOut", true);
      return;
    }

    const targetLocationNode = this.highlightedLocationId
      ? this.locationNodes.get(this.highlightedLocationId)
      : undefined;
    if (targetLocationNode) {
      camera.pan(
        targetLocationNode.body.x,
        targetLocationNode.body.y,
        320,
        "Sine.easeInOut",
        true
      );
      return;
    }

    camera.pan(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, 320, "Sine.easeInOut", true);
  }

  private showTooltip(x: number, y: number, text: string): void {
    if (!this.tooltip) {
      return;
    }

    const width = Math.min(220, Math.max(120, text.length * 7 + 18));
    this.tooltip.box.setPosition(x, y);
    this.tooltip.box.setSize(width, 30);
    this.tooltip.box.setVisible(true);
    this.tooltip.text.setPosition(x, y);
    this.tooltip.text.setText(text);
    this.tooltip.text.setVisible(true);
  }

  private hideTooltip(): void {
    if (!this.tooltip) {
      return;
    }
    this.tooltip.box.setVisible(false);
    this.tooltip.text.setVisible(false);
  }

  private playTapFeedback(...targets: Phaser.GameObjects.GameObject[]): void {
    this.tweens.add({
      targets,
      scale: { from: 1, to: 1.08 },
      duration: 110,
      yoyo: true,
      ease: "Quad.Out",
    });
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

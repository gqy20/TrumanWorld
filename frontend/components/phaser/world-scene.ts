import * as Phaser from "phaser";

import type { SceneAgent, SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";
import { getHeatLevel } from "@/lib/world-utils";
import {
  AGENT_TEXTURE_SIZE,
  BUILDING_TEXTURE_SIZE,
  CANVAS_HEIGHT,
  CANVAS_WIDTH,
  GROUND_TEXTURE_SIZE,
  LOCATION_HEIGHT,
  LOCATION_WIDTH,
  PIXEL_SCALE,
  SCENE_PADDING_X,
  SCENE_PADDING_Y,
  getAgentColor,
  getAgentMarker,
  getAgentTextureKey,
  getArrowAngleDegrees,
  getConfiguredAgentTextureKey,
  getConfiguredLocationTextureKey,
  getLocationColor,
  getLocationGlyph,
  getStagePalette,
  mergeStagePalette,
  parseRgbaColor,
} from "./world-scene-style";

type LocationNode = {
  glow: Phaser.GameObjects.Arc;
  body: Phaser.GameObjects.Image;
  icon: Phaser.GameObjects.Text;
  label: Phaser.GameObjects.Text;
  badge: Phaser.GameObjects.Text;
  pulseTween?: Phaser.Tweens.Tween;
};

type AgentNode = {
  body: Phaser.GameObjects.Image;
  marker: Phaser.GameObjects.Text;
  label: Phaser.GameObjects.Text;
  pulseTween?: Phaser.Tweens.Tween;
};

type TrailNode = {
  line: Phaser.GameObjects.Line;
  arrow: Phaser.GameObjects.Triangle;
  label: Phaser.GameObjects.Text;
  fadeTween?: Phaser.Tweens.Tween;
};

type BubbleNode = {
  box: Phaser.GameObjects.Rectangle;
  text: Phaser.GameObjects.Text;
  floatTween?: Phaser.Tweens.Tween;
};

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

  private syncLocations(locations: SceneLocation[]): void {
    const activeIds = new Set(locations.map((location) => location.id));

    for (const [locationId, node] of this.locationNodes.entries()) {
      if (activeIds.has(locationId)) {
        continue;
      }
      node.pulseTween?.stop();
      node.glow.destroy();
      node.body.destroy();
      node.icon.destroy();
      node.label.destroy();
      node.badge.destroy();
      this.locationNodes.delete(locationId);
    }

    for (const location of locations) {
      const point = this.mapWorldToCanvas(location.x, location.y, locations);
      const existing = this.locationNodes.get(location.id);
      const occupantRatio =
        location.capacity > 0 ? Math.min(location.occupantCount / location.capacity, 1) : 0;
      const alpha = 0.42 + occupantRatio * 0.45;
      const heatLevel = getHeatLevel(location.heat);

      if (existing) {
        this.ensureLocationTexture(location);
        existing.glow.setPosition(point.x, point.y);
        existing.glow.setScale((38 + location.heat * 18) / 38);
        existing.glow.setFillStyle(
          Number.parseInt(heatLevel.color.replace("#", ""), 16),
          0.08 + location.heat * 0.22
        );
        existing.body.setPosition(point.x, point.y);
        existing.body.setTexture(
          getConfiguredLocationTextureKey(
            location.visual.visualPreset ?? location.locationType,
            location.locationType
          )
        );
        existing.body.setAlpha(alpha);
        existing.icon.setPosition(point.x, point.y - 18);
        existing.icon.setText(location.visual.glyph ?? getLocationGlyph(location.locationType));
        existing.label.setPosition(point.x, point.y - 6);
        existing.label.setText(location.name);
        existing.badge.setPosition(point.x, point.y + 12);
        existing.badge.setText(`${location.occupantCount}/${location.capacity}`);
        continue;
      }

      const glow = this.add
        .circle(point.x, point.y, 38 + location.heat * 18, Number.parseInt(heatLevel.color.replace("#", ""), 16), 0.08 + location.heat * 0.22)
        .setDepth(8);
      this.ensureLocationTexture(location);
      const body = this.add
        .image(
          point.x,
          point.y,
          getConfiguredLocationTextureKey(
            location.visual.visualPreset ?? location.locationType,
            location.locationType
          )
        )
        .setDisplaySize(LOCATION_WIDTH, LOCATION_HEIGHT)
        .setAlpha(alpha)
        .setDepth(10)
        .setInteractive({ cursor: "pointer" });
      const icon = this.add
        .text(point.x, point.y - 18, location.visual.glyph ?? getLocationGlyph(location.locationType), {
          color: "#f8fafc",
          fontFamily: "ui-monospace, SFMono-Regular, monospace",
          fontSize: "14px",
          fontStyle: "700",
        })
        .setOrigin(0.5)
        .setDepth(11);
      const label = this.add
        .text(point.x, point.y - 6, location.name, {
          color: "#e2e8f0",
          fontFamily: "ui-monospace, SFMono-Regular, monospace",
          fontSize: "12px",
          fontStyle: "600",
        })
        .setOrigin(0.5)
        .setDepth(11);
      const badge = this.add
        .text(point.x, point.y + 12, `${location.occupantCount}/${location.capacity}`, {
          color: "#cbd5e1",
          fontFamily: "ui-monospace, SFMono-Regular, monospace",
          fontSize: "10px",
        })
        .setOrigin(0.5)
        .setDepth(11);

      body.on("pointerdown", () => {
        this.playTapFeedback(body, icon, label, badge);
        this.events.emit("location:click", location.id);
      });
      body.on("pointerover", () => {
        this.showTooltip(point.x, point.y - 48, `${location.name} / ${location.locationType}`);
      });
      body.on("pointerout", () => {
        this.hideTooltip();
      });

      const pulseTween =
        location.heat >= 0.18
          ? this.tweens.add({
              targets: glow,
              alpha: { from: 0.14, to: 0.32 + Math.min(location.heat, 0.6) * 0.18 },
              scale: { from: 0.92, to: 1.08 + location.heat * 0.08 },
              duration: 1400,
              yoyo: true,
              repeat: -1,
              ease: "Sine.InOut",
            })
          : undefined;

      this.locationNodes.set(location.id, { glow, body, icon, label, badge, pulseTween });
    }

    this.refreshLocationHighlights();
  }

  private syncAgents(agents: SceneAgent[], locations: SceneLocation[]): void {
    const locationMap = new Map(locations.map((location) => [location.id, location]));
    const activeIds = new Set(agents.map((agent) => agent.id));

    for (const [agentId, node] of this.agentNodes.entries()) {
      if (activeIds.has(agentId)) {
        continue;
      }
      node.pulseTween?.stop();
      node.body.destroy();
      node.marker.destroy();
      node.label.destroy();
      this.agentNodes.delete(agentId);
    }

    for (const agent of agents) {
      const location = locationMap.get(agent.locationId);
      if (!location) {
        continue;
      }

      const point = this.getAgentPosition(location, agent.slotIndex);
      const existing = this.agentNodes.get(agent.id);

      if (existing) {
        this.tweens.add({
          targets: existing.body,
          x: point.x,
          y: point.y,
          duration: 260,
          ease: "Quad.Out",
        });
        this.tweens.add({
          targets: existing.marker,
          x: point.x,
          y: point.y - 14,
          duration: 260,
          ease: "Quad.Out",
        });
        this.tweens.add({
          targets: existing.label,
          x: point.x,
          y: point.y + 14,
          duration: 260,
          ease: "Quad.Out",
        });
        this.ensureAgentTexture(agent);
        existing.body.setTexture(
          getConfiguredAgentTextureKey(agent.visual?.visualPreset ?? "default", agent.status)
        );
        existing.body.setAlpha(1);
        existing.marker.setText(agent.visual?.marker ?? getAgentMarker(agent.status));
        existing.label.setText(agent.name);
        continue;
      }

      this.ensureAgentTexture(agent);
      const body = this.add
        .image(
          point.x,
          point.y,
          getConfiguredAgentTextureKey(agent.visual?.visualPreset ?? "default", agent.status)
        )
        .setDisplaySize(AGENT_TEXTURE_SIZE * PIXEL_SCALE, AGENT_TEXTURE_SIZE * PIXEL_SCALE)
        .setDepth(20)
        .setInteractive({ cursor: "pointer" });
      const marker = this.add
        .text(point.x, point.y - 14, agent.visual?.marker ?? getAgentMarker(agent.status), {
          color: "#cbd5e1",
          fontFamily: "ui-monospace, SFMono-Regular, monospace",
          fontSize: "10px",
          fontStyle: "700",
        })
        .setOrigin(0.5)
        .setDepth(21);
      const label = this.add
        .text(point.x, point.y + 14, agent.name, {
          color: "#f8fafc",
          fontFamily: "ui-monospace, SFMono-Regular, monospace",
          fontSize: "10px",
        })
        .setOrigin(0.5, 0)
        .setDepth(21);

      body.on("pointerdown", () => {
        this.playTapFeedback(body, marker, label);
        this.events.emit("agent:click", agent.id);
      });
      body.on("pointerover", () => {
        this.showTooltip(point.x, point.y - 34, `${agent.name} / ${agent.status}`);
      });
      body.on("pointerout", () => {
        this.hideTooltip();
      });

      this.agentNodes.set(agent.id, { body, marker, label });
    }

    this.refreshAgentHighlights();
  }

  private syncMoveTrails(world: SceneWorld): void {
    const activeIds = new Set(world.moveTrails.map((trail) => trail.id));
    const locationMap = new Map(world.locations.map((location) => [location.id, location]));

    for (const [trailId, node] of this.trailNodes.entries()) {
      if (activeIds.has(trailId)) {
        continue;
      }
      node.fadeTween?.stop();
      node.line.destroy();
      node.arrow.destroy();
      node.label.destroy();
      this.trailNodes.delete(trailId);
    }

    for (const trail of world.moveTrails) {
      const fromLocation = locationMap.get(trail.fromLocationId);
      const toLocation = locationMap.get(trail.toLocationId);
      if (!fromLocation || !toLocation) {
        continue;
      }

      const fromPoint = this.mapWorldToCanvas(fromLocation.x, fromLocation.y, world.locations);
      const toPoint = this.mapWorldToCanvas(toLocation.x, toLocation.y, world.locations);
      const midX = (fromPoint.x + toPoint.x) / 2;
      const midY = (fromPoint.y + toPoint.y) / 2 - 18;
      const recencyAlpha = Math.max(0.25, 0.68 - trail.recencyIndex * 0.14);
      const arrowX = fromPoint.x + (toPoint.x - fromPoint.x) * 0.78;
      const arrowY = fromPoint.y + (toPoint.y - fromPoint.y) * 0.78;
      const arrowAngle = getArrowAngleDegrees(fromPoint.x, fromPoint.y, toPoint.x, toPoint.y);
      const existing = this.trailNodes.get(trail.id);

      if (existing) {
        existing.line.setTo(fromPoint.x, fromPoint.y, toPoint.x, toPoint.y);
        existing.line.setAlpha(recencyAlpha);
        existing.arrow.setPosition(arrowX, arrowY);
        existing.arrow.setRotation(Phaser.Math.DegToRad(arrowAngle));
        existing.arrow.setAlpha(recencyAlpha);
        existing.label.setPosition(midX, midY);
        existing.label.setText(`${trail.actorName} →`);
        existing.label.setAlpha(recencyAlpha);
        continue;
      }

      const line = this.add
        .line(0, 0, fromPoint.x, fromPoint.y, toPoint.x, toPoint.y, 0x38bdf8, 0.55)
        .setOrigin(0, 0)
        .setLineWidth(2, 2)
        .setDepth(14)
        .setAlpha(recencyAlpha);
      const arrow = this.add
        .triangle(arrowX, arrowY, 0, 10, 7, -6, -7, -6, 0x7dd3fc, recencyAlpha)
        .setDepth(15)
        .setRotation(Phaser.Math.DegToRad(arrowAngle));
      const label = this.add
        .text(midX, midY, `${trail.actorName} →`, {
          color: "#7dd3fc",
          fontFamily: "ui-monospace, SFMono-Regular, monospace",
          fontSize: "10px",
        })
        .setOrigin(0.5)
        .setDepth(16)
        .setAlpha(recencyAlpha);

      const fadeTween = this.tweens.add({
        targets: [line, arrow, label],
        alpha: { from: recencyAlpha, to: Math.max(0.12, recencyAlpha - 0.18) },
        duration: 1800 + trail.recencyIndex * 300,
        yoyo: true,
        repeat: -1,
        ease: "Sine.InOut",
      });

      this.trailNodes.set(trail.id, { line, arrow, label, fadeTween });
    }
  }

  private syncBubbles(world: SceneWorld): void {
    const activeIds = new Set(world.bubbles.map((bubble) => bubble.id));
    const locationMap = new Map(world.locations.map((location) => [location.id, location]));
    const agentMap = new Map(world.agents.map((agent) => [agent.id, agent]));

    for (const [bubbleId, node] of this.bubbleNodes.entries()) {
      if (activeIds.has(bubbleId)) {
        continue;
      }
      node.floatTween?.stop();
      node.box.destroy();
      node.text.destroy();
      this.bubbleNodes.delete(bubbleId);
    }

    for (const bubble of world.bubbles) {
      const location = locationMap.get(bubble.locationId);
      if (!location) {
        continue;
      }

      const speakingAgent = bubble.speakerAgentId ? agentMap.get(bubble.speakerAgentId) : undefined;
      const anchorPoint = speakingAgent
        ? this.getAgentPosition(location, speakingAgent.slotIndex)
        : this.mapWorldToCanvas(location.x, location.y, world.locations);
      const bubbleX = anchorPoint.x;
      const bubbleY = anchorPoint.y - 30 - bubble.recencyIndex * 16;
      const textValue = `${bubble.speakerName}: ${bubble.text}`;
      const bubbleWidth = Math.min(210, Math.max(120, textValue.length * 6.5));
      const bubbleAlpha = Math.max(0.48, 0.92 - bubble.recencyIndex * 0.16);
      const existing = this.bubbleNodes.get(bubble.id);

      if (existing) {
        existing.box.setPosition(bubbleX, bubbleY);
        existing.box.setSize(bubbleWidth, 28);
        existing.box.setAlpha(bubbleAlpha);
        existing.text.setPosition(bubbleX, bubbleY);
        existing.text.setText(textValue);
        existing.text.setAlpha(bubbleAlpha);
        continue;
      }

      const box = this.add
        .rectangle(bubbleX, bubbleY, bubbleWidth, 28, 0xf8fafc, bubbleAlpha)
        .setStrokeStyle(1, 0xcbd5e1, 0.9)
        .setDepth(30);
      const text = this.add
        .text(bubbleX, bubbleY, textValue, {
          color: "#0f172a",
          fontFamily: "ui-monospace, SFMono-Regular, monospace",
          fontSize: "10px",
        })
        .setOrigin(0.5)
        .setDepth(31)
        .setAlpha(bubbleAlpha);

      const floatTween = this.tweens.add({
        targets: [box, text],
        y: `-=${8 + bubble.recencyIndex * 2}`,
        alpha: { from: bubbleAlpha, to: Math.max(0.22, bubbleAlpha - 0.28) },
        duration: 1400 + bubble.recencyIndex * 180,
        yoyo: true,
        repeat: -1,
        ease: "Sine.InOut",
      });

      this.bubbleNodes.set(bubble.id, { box, text, floatTween });
    }
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
    const center = this.mapWorldToCanvas(
      location.x,
      location.y,
      this.currentWorld?.locations ?? [location],
    );
    const columns = 3;
    const col = slotIndex % columns;
    const row = Math.floor(slotIndex / columns);
    const offsetX = (col - 1) * 18;
    const offsetY = 34 + row * 18;
    return {
      x: center.x + offsetX,
      y: center.y + offsetY,
    };
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
    if (locations.length === 0) {
      return { x: CANVAS_WIDTH / 2, y: CANVAS_HEIGHT / 2 };
    }

    const xs = locations.map((location) => location.x);
    const ys = locations.map((location) => location.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const width = maxX - minX;
    const height = maxY - minY;

    const normalizedX =
      width === 0
        ? 0.5
        : (x - minX) / width;
    const normalizedY =
      height === 0
        ? 0.5
        : (y - minY) / height;

    return {
      x: SCENE_PADDING_X + normalizedX * (CANVAS_WIDTH - SCENE_PADDING_X * 2),
      y: SCENE_PADDING_Y + normalizedY * (CANVAS_HEIGHT - SCENE_PADDING_Y * 2),
    };
  }

  private createPixelTextures(): void {
    if (!this.textures.exists("pixel-ground")) {
      this.generateGroundTexture("pixel-ground", "default");
    }

    const statuses: SceneAgent["status"][] = [
      "idle",
      "moving",
      "talking",
      "working",
      "resting",
    ];
    for (const preset of ["default", "student", "resident"]) {
      for (const status of statuses) {
        const key =
          preset === "default"
            ? getAgentTextureKey(status)
            : getConfiguredAgentTextureKey(preset, status);
        if (!this.textures.exists(key)) {
          this.generateAgentTexture(key, status, preset);
        }
      }
    }
  }

  private ensureGroundTexture(groundPreset: string): string {
    const key = groundPreset === "default" ? "pixel-ground" : `pixel-ground-${groundPreset}`;
    if (!this.textures.exists(key)) {
      this.generateGroundTexture(key, groundPreset);
    }
    return key;
  }

  private ensureLocationTexture(location: SceneLocation): void {
    const visualPreset = location.visual.visualPreset ?? location.locationType;
    const textureKey = getConfiguredLocationTextureKey(visualPreset, location.locationType);
    if (!this.textures.exists(textureKey)) {
      this.generateBuildingTexture(textureKey, location.locationType, visualPreset);
    }
  }

  private ensureAgentTexture(agent: SceneAgent): void {
    const preset = agent.visual?.visualPreset ?? "default";
    const key = getConfiguredAgentTextureKey(preset, agent.status);
    if (!this.textures.exists(key)) {
      this.generateAgentTexture(key, agent.status, preset);
    }
  }

  private generateGroundTexture(key: string, groundPreset: string): void {
    const graphics = this.make.graphics({ x: 0, y: 0 }, false);

    switch (groundPreset) {
      case "lawn":
        graphics.fillStyle(0x16351f, 1);
        graphics.fillRect(0, 0, GROUND_TEXTURE_SIZE, GROUND_TEXTURE_SIZE);
        graphics.fillStyle(0x1f6b36, 1);
        for (let x = 0; x < GROUND_TEXTURE_SIZE; x += 6) {
          graphics.fillRect(x, 6, 2, 3);
          graphics.fillRect(x + 1, 16, 2, 4);
          graphics.fillRect(x + 3, 25, 2, 3);
        }
        break;
      case "plaza":
        graphics.fillStyle(0x2c3444, 1);
        graphics.fillRect(0, 0, GROUND_TEXTURE_SIZE, GROUND_TEXTURE_SIZE);
        graphics.fillStyle(0x455066, 1);
        for (let x = 0; x < GROUND_TEXTURE_SIZE; x += 8) {
          graphics.fillRect(x, 0, 1, GROUND_TEXTURE_SIZE);
        }
        for (let y = 0; y < GROUND_TEXTURE_SIZE; y += 8) {
          graphics.fillRect(0, y, GROUND_TEXTURE_SIZE, 1);
        }
        break;
      case "boardwalk":
      default:
        graphics.fillStyle(0x16233a, 1);
        graphics.fillRect(0, 0, GROUND_TEXTURE_SIZE, GROUND_TEXTURE_SIZE);
        graphics.fillStyle(0x1d2f4f, 1);
        graphics.fillRect(0, 0, GROUND_TEXTURE_SIZE, 10);
        graphics.fillStyle(0x203456, 1);
        graphics.fillRect(0, 10, GROUND_TEXTURE_SIZE, GROUND_TEXTURE_SIZE - 10);
        graphics.fillStyle(0x2a4365, 1);
        for (let x = 0; x < GROUND_TEXTURE_SIZE; x += 8) {
          graphics.fillRect(x, 9, 4, 1);
          graphics.fillRect(x + 2, 18, 2, 1);
          graphics.fillRect(x + 1, 26, 3, 1);
        }
        graphics.fillStyle(0x101827, 0.8);
        for (let y = 0; y < GROUND_TEXTURE_SIZE; y += 8) {
          graphics.fillRect(0, y, GROUND_TEXTURE_SIZE, 1);
        }
        break;
    }

    graphics.generateTexture(key, GROUND_TEXTURE_SIZE, GROUND_TEXTURE_SIZE);
    graphics.destroy();
  }

  private generateBuildingTexture(key: string, locationType: string, visualPreset: string): void {
    const graphics = this.make.graphics({ x: 0, y: 0 }, false);
    const baseColor = getLocationColor(locationType);
    const roofColor = Phaser.Display.Color.IntegerToColor(baseColor).darken(20).color;
    const lightColor = Phaser.Display.Color.IntegerToColor(baseColor).lighten(25).color;
    const darkColor = Phaser.Display.Color.IntegerToColor(baseColor).darken(35).color;

    graphics.fillStyle(0x0b1220, 0.5);
    graphics.fillRect(5, 20, 14, 2);

    switch (visualPreset) {
      case "shop":
      case "cafe":
        graphics.fillStyle(roofColor, 1);
        graphics.fillRect(4, 5, 16, 3);
        graphics.fillStyle(baseColor, 1);
        graphics.fillRect(5, 8, 14, 10);
        graphics.fillStyle(0xf8fafc, 1);
        graphics.fillRect(5, 9, 14, 2);
        graphics.fillStyle(lightColor, 1);
        graphics.fillRect(7, 12, 4, 3);
        graphics.fillRect(13, 12, 4, 3);
        graphics.fillStyle(darkColor, 1);
        graphics.fillRect(10, 14, 4, 4);
        break;
      case "grove":
      case "park":
      case "quad":
        graphics.fillStyle(0x14532d, 1);
        graphics.fillRect(5, 18, 14, 3);
        graphics.fillStyle(0x22c55e, 1);
        graphics.fillRect(7, 10, 10, 8);
        graphics.fillRect(4, 12, 4, 5);
        graphics.fillRect(16, 12, 4, 5);
        graphics.fillStyle(0x166534, 1);
        graphics.fillRect(10, 16, 4, 2);
        graphics.fillStyle(0x854d0e, 1);
        graphics.fillRect(10, 18, 4, 3);
        break;
      case "tower":
      case "office":
        graphics.fillStyle(roofColor, 1);
        graphics.fillRect(6, 3, 12, 3);
        graphics.fillStyle(baseColor, 1);
        graphics.fillRect(6, 6, 12, 14);
        graphics.fillStyle(lightColor, 1);
        for (const x of [8, 12, 16]) {
          for (const y of [8, 12, 16]) {
            graphics.fillRect(x, y, 2, 2);
          }
        }
        graphics.fillStyle(darkColor, 1);
        graphics.fillRect(10, 18, 4, 2);
        break;
      case "house":
      case "home":
      case "dorm":
        graphics.fillStyle(roofColor, 1);
        graphics.fillRect(4, 6, 16, 4);
        graphics.fillStyle(baseColor, 1);
        graphics.fillRect(6, 10, 12, 9);
        graphics.fillStyle(lightColor, 1);
        graphics.fillRect(8, 12, 3, 3);
        graphics.fillRect(13, 12, 3, 3);
        graphics.fillStyle(darkColor, 1);
        graphics.fillRect(11, 15, 3, 4);
        break;
      case "hall":
      case "library":
      case "lecture_hall":
        graphics.fillStyle(roofColor, 1);
        graphics.fillRect(3, 5, 18, 3);
        graphics.fillStyle(baseColor, 1);
        graphics.fillRect(5, 8, 14, 10);
        graphics.fillStyle(lightColor, 1);
        for (const x of [7, 11, 15]) {
          graphics.fillRect(x, 10, 2, 6);
        }
        graphics.fillStyle(darkColor, 1);
        graphics.fillRect(10, 15, 4, 3);
        break;
      case "square":
      case "plaza":
        graphics.fillStyle(roofColor, 1);
        graphics.fillRect(6, 18, 12, 2);
        graphics.fillStyle(baseColor, 1);
        graphics.fillRect(7, 8, 10, 10);
        graphics.fillStyle(lightColor, 1);
        graphics.fillRect(10, 5, 4, 3);
        graphics.fillRect(9, 11, 6, 2);
        graphics.fillStyle(0xe2e8f0, 1);
        graphics.fillRect(10, 13, 4, 4);
        break;
      default:
        graphics.fillStyle(roofColor, 1);
        graphics.fillRect(4, 5, 16, 3);
        graphics.fillStyle(baseColor, 1);
        graphics.fillRect(5, 8, 14, 10);
        graphics.fillStyle(lightColor, 1);
        graphics.fillRect(8, 11, 3, 3);
        graphics.fillRect(13, 11, 3, 3);
        graphics.fillStyle(darkColor, 1);
        graphics.fillRect(10, 14, 4, 4);
        break;
    }

    graphics.lineStyle(1, 0xe2e8f0, 0.45);
    graphics.strokeRect(5, 8, 14, 10);
    graphics.generateTexture(key, BUILDING_TEXTURE_SIZE, BUILDING_TEXTURE_SIZE);
    graphics.destroy();
  }

  private generateAgentTexture(
    key: string,
    status: SceneAgent["status"],
    visualPreset: string,
  ): void {
    const graphics = this.make.graphics({ x: 0, y: 0 }, false);
    const bodyColor = getAgentColor(status);
    const accentColor = Phaser.Display.Color.IntegerToColor(bodyColor).lighten(18).color;

    switch (visualPreset) {
      case "student":
        graphics.fillStyle(0x0f172a, 1);
        graphics.fillRect(5, 1, 6, 4);
        graphics.fillStyle(accentColor, 1);
        graphics.fillRect(4, 5, 8, 4);
        graphics.fillStyle(bodyColor, 1);
        graphics.fillRect(3, 9, 10, 4);
        graphics.fillRect(4, 13, 3, 3);
        graphics.fillRect(9, 13, 3, 3);
        graphics.fillStyle(0xe2e8f0, 1);
        graphics.fillRect(11, 5, 1, 8);
        break;
      case "resident":
        graphics.fillStyle(0xf5d0fe, 1);
        graphics.fillRect(5, 1, 6, 4);
        graphics.fillStyle(accentColor, 1);
        graphics.fillRect(4, 5, 8, 3);
        graphics.fillStyle(bodyColor, 1);
        graphics.fillRect(3, 8, 10, 5);
        graphics.fillRect(4, 13, 3, 3);
        graphics.fillRect(9, 13, 3, 3);
        graphics.fillStyle(0x1f2937, 1);
        graphics.fillRect(2, 9, 1, 3);
        graphics.fillRect(13, 9, 1, 3);
        break;
      default:
        graphics.fillStyle(0x0f172a, 1);
        graphics.fillRect(5, 1, 6, 4);
        graphics.fillStyle(accentColor, 1);
        graphics.fillRect(4, 5, 8, 4);
        graphics.fillStyle(bodyColor, 1);
        graphics.fillRect(3, 9, 10, 4);
        graphics.fillRect(4, 13, 3, 3);
        graphics.fillRect(9, 13, 3, 3);
        break;
    }
    graphics.generateTexture(key, AGENT_TEXTURE_SIZE, AGENT_TEXTURE_SIZE);
    graphics.destroy();
  }
}

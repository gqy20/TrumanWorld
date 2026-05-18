import * as Phaser from "phaser";

import type { SceneAgent, SceneLocation, SceneWorld } from "@/lib/world-scene-adapter";
import { getHeatLevel } from "@/lib/world-utils";

import {
  TOWN_SPRITESHEET_KEY,
  getAgentAssetFrame,
  getLocationAssetFrame,
} from "./world-asset-pack";
import {
  AGENT_TEXTURE_SIZE,
  LOCATION_HEIGHT,
  LOCATION_WIDTH,
  PIXEL_SCALE,
  getAgentMarker,
  getArrowAngleDegrees,
  getLocationGlyph,
} from "./world-scene-style";

export type LocationNode = {
  glow: Phaser.GameObjects.Arc;
  body: Phaser.GameObjects.Image;
  icon: Phaser.GameObjects.Text;
  label: Phaser.GameObjects.Text;
  badge: Phaser.GameObjects.Text;
  pulseTween?: Phaser.Tweens.Tween;
};

export type AgentNode = {
  body: Phaser.GameObjects.Image;
  marker: Phaser.GameObjects.Text;
  label: Phaser.GameObjects.Text;
  pulseTween?: Phaser.Tweens.Tween;
};

export type TrailNode = {
  line: Phaser.GameObjects.Line;
  arrow: Phaser.GameObjects.Triangle;
  label: Phaser.GameObjects.Text;
  fadeTween?: Phaser.Tweens.Tween;
};

export type BubbleNode = {
  box: Phaser.GameObjects.Rectangle;
  text: Phaser.GameObjects.Text;
  floatTween?: Phaser.Tweens.Tween;
};

type CanvasPoint = {
  x: number;
  y: number;
};

type SceneSyncContext = {
  scene: Phaser.Scene;
  ensureLocationTexture: (location: SceneLocation) => void;
  ensureAgentTexture: (agent: SceneAgent) => void;
  mapWorldToCanvas: (x: number, y: number, locations: SceneLocation[]) => CanvasPoint;
  getAgentPosition: (location: SceneLocation, slotIndex: number) => CanvasPoint;
  playTapFeedback: (...targets: Phaser.GameObjects.GameObject[]) => void;
  showTooltip: (x: number, y: number, text: string) => void;
  hideTooltip: () => void;
};

export function syncLocations(
  context: SceneSyncContext,
  locationNodes: Map<string, LocationNode>,
  locations: SceneLocation[],
): void {
  const activeIds = new Set(locations.map((location) => location.id));

  for (const [locationId, node] of locationNodes.entries()) {
    if (activeIds.has(locationId)) {
      continue;
    }
    node.pulseTween?.stop();
    node.glow.destroy();
    node.body.destroy();
    node.icon.destroy();
    node.label.destroy();
    node.badge.destroy();
    locationNodes.delete(locationId);
  }

  for (const location of locations) {
    const point = context.mapWorldToCanvas(location.x, location.y, locations);
    const existing = locationNodes.get(location.id);
    const occupantRatio =
      location.capacity > 0 ? Math.min(location.occupantCount / location.capacity, 1) : 0;
    const alpha = 0.92 + occupantRatio * 0.08;
    const heatLevel = getHeatLevel(location.heat);
    const baseDepth = Math.round(point.y);
    const assetFrame = getLocationAssetFrame(location);

    if (existing) {
      context.ensureLocationTexture(location);
      existing.glow.setPosition(point.x, point.y + 18);
      existing.glow.setScale((38 + location.heat * 18) / 38);
      existing.glow.setFillStyle(
        Number.parseInt(heatLevel.color.replace("#", ""), 16),
        0.08 + location.heat * 0.22,
      );
      existing.glow.setDepth(baseDepth - 6);
      existing.body.setPosition(point.x, point.y - 28);
      existing.body.setTexture(TOWN_SPRITESHEET_KEY, assetFrame);
      existing.body.setAlpha(alpha);
      existing.body.setDepth(baseDepth + 2);
      existing.icon.setPosition(point.x, point.y - 54);
      existing.icon.setText(location.visual.glyph ?? getLocationGlyph(location.locationType));
      existing.icon.setDepth(baseDepth + 3);
      existing.label.setPosition(point.x, point.y - 10);
      existing.label.setText(location.name);
      existing.label.setAlpha(0);
      existing.label.setDepth(baseDepth + 3);
      existing.badge.setPosition(point.x, point.y + 10);
      existing.badge.setText(`${location.occupantCount}/${location.capacity}`);
      existing.badge.setAlpha(0);
      existing.badge.setDepth(baseDepth + 3);
      continue;
    }

    const glow = context.scene.add
      .circle(
        point.x,
        point.y + 18,
        38 + location.heat * 18,
        Number.parseInt(heatLevel.color.replace("#", ""), 16),
        0.08 + location.heat * 0.22,
      )
      .setScale(1.4, 0.42)
      .setDepth(baseDepth - 6);
    context.ensureLocationTexture(location);
    const body = context.scene.add
      .image(point.x, point.y - 28, TOWN_SPRITESHEET_KEY, assetFrame)
      .setDisplaySize(LOCATION_WIDTH, LOCATION_HEIGHT)
      .setAlpha(alpha)
      .setDepth(baseDepth + 2)
      .setInteractive({ cursor: "pointer" });
    const icon = context.scene.add
      .text(point.x, point.y - 54, location.visual.glyph ?? getLocationGlyph(location.locationType), {
        color: "#f8fafc",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "14px",
        fontStyle: "700",
      })
      .setOrigin(0.5)
      .setDepth(baseDepth + 3);
    const label = context.scene.add
      .text(point.x, point.y - 10, location.name, {
        color: "#e2e8f0",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "12px",
        fontStyle: "600",
      })
      .setOrigin(0.5)
      .setAlpha(0)
      .setDepth(baseDepth + 3);
    const badge = context.scene.add
      .text(point.x, point.y + 10, `${location.occupantCount}/${location.capacity}`, {
        color: "#cbd5e1",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "10px",
      })
      .setOrigin(0.5)
      .setAlpha(0)
      .setDepth(baseDepth + 3);

    body.on("pointerdown", () => {
      context.playTapFeedback(body, icon, label, badge);
      context.scene.events.emit("location:click", location.id);
    });
    body.on("pointerover", () => {
      label.setAlpha(1);
      badge.setAlpha(1);
      context.showTooltip(point.x, point.y - 92, `${location.name} / ${location.locationType}`);
    });
    body.on("pointerout", () => {
      label.setAlpha(0);
      badge.setAlpha(0);
      context.hideTooltip();
    });

    const pulseTween =
      location.heat >= 0.18
        ? context.scene.tweens.add({
            targets: glow,
            alpha: { from: 0.14, to: 0.32 + Math.min(location.heat, 0.6) * 0.18 },
            scale: { from: 0.92, to: 1.08 + location.heat * 0.08 },
            duration: 1400,
            yoyo: true,
            repeat: -1,
            ease: "Sine.InOut",
          })
        : undefined;

    locationNodes.set(location.id, { glow, body, icon, label, badge, pulseTween });
  }
}

export function syncAgents(
  context: SceneSyncContext,
  agentNodes: Map<string, AgentNode>,
  agents: SceneAgent[],
  locations: SceneLocation[],
): void {
  const locationMap = new Map(locations.map((location) => [location.id, location]));
  const activeIds = new Set(agents.map((agent) => agent.id));

  for (const [agentId, node] of agentNodes.entries()) {
    if (activeIds.has(agentId)) {
      continue;
    }
    node.pulseTween?.stop();
    node.body.destroy();
    node.marker.destroy();
    node.label.destroy();
    agentNodes.delete(agentId);
  }

  for (const agent of agents) {
    const location = locationMap.get(agent.locationId);
    if (!location) {
      continue;
    }

    const point = context.getAgentPosition(location, agent.slotIndex);
    const existing = agentNodes.get(agent.id);
    const agentDepth = Math.round(point.y + 24);
    const assetFrame = getAgentAssetFrame(agent);

    if (existing) {
      context.scene.tweens.add({
        targets: existing.body,
        x: point.x,
        y: point.y,
        duration: 260,
        ease: "Quad.Out",
      });
      context.scene.tweens.add({
        targets: existing.marker,
        x: point.x,
        y: point.y - 14,
        duration: 260,
        ease: "Quad.Out",
      });
      context.scene.tweens.add({
        targets: existing.label,
        x: point.x,
        y: point.y + 14,
        duration: 260,
        ease: "Quad.Out",
      });
      context.ensureAgentTexture(agent);
      existing.body.setTexture(TOWN_SPRITESHEET_KEY, assetFrame);
      existing.body.setAlpha(1);
      existing.body.setDepth(agentDepth);
      existing.marker.setText(agent.visual?.marker ?? getAgentMarker(agent.status));
      existing.marker.setDepth(agentDepth + 1);
      existing.label.setText(agent.name);
      existing.label.setAlpha(0);
      existing.label.setDepth(agentDepth + 1);
      continue;
    }

    context.ensureAgentTexture(agent);
    const body = context.scene.add
      .image(point.x, point.y, TOWN_SPRITESHEET_KEY, assetFrame)
      .setDisplaySize(AGENT_TEXTURE_SIZE * PIXEL_SCALE, AGENT_TEXTURE_SIZE * PIXEL_SCALE)
      .setDepth(agentDepth)
      .setInteractive({ cursor: "pointer" });
    const marker = context.scene.add
      .text(point.x, point.y - 14, agent.visual?.marker ?? getAgentMarker(agent.status), {
        color: "#cbd5e1",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "10px",
        fontStyle: "700",
      })
      .setOrigin(0.5)
      .setDepth(agentDepth + 1);
    const label = context.scene.add
      .text(point.x, point.y + 14, agent.name, {
        color: "#f8fafc",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "10px",
      })
      .setOrigin(0.5, 0)
      .setAlpha(0)
      .setDepth(agentDepth + 1);

    body.on("pointerdown", () => {
      context.playTapFeedback(body, marker, label);
      context.scene.events.emit("agent:click", agent.id);
    });
    body.on("pointerover", () => {
      label.setAlpha(1);
      context.showTooltip(point.x, point.y - 34, `${agent.name} / ${agent.status}`);
    });
    body.on("pointerout", () => {
      label.setAlpha(0);
      context.hideTooltip();
    });

    agentNodes.set(agent.id, { body, marker, label });
  }
}

export function syncMoveTrails(
  context: SceneSyncContext,
  trailNodes: Map<string, TrailNode>,
  world: SceneWorld,
): void {
  const activeIds = new Set(world.moveTrails.map((trail) => trail.id));
  const locationMap = new Map(world.locations.map((location) => [location.id, location]));

  for (const [trailId, node] of trailNodes.entries()) {
    if (activeIds.has(trailId)) {
      continue;
    }
    node.fadeTween?.stop();
    node.line.destroy();
    node.arrow.destroy();
    node.label.destroy();
    trailNodes.delete(trailId);
  }

  for (const trail of world.moveTrails) {
    const fromLocation = locationMap.get(trail.fromLocationId);
    const toLocation = locationMap.get(trail.toLocationId);
    if (!fromLocation || !toLocation) {
      continue;
    }

    const fromPoint = context.mapWorldToCanvas(fromLocation.x, fromLocation.y, world.locations);
    const toPoint = context.mapWorldToCanvas(toLocation.x, toLocation.y, world.locations);
    const midX = (fromPoint.x + toPoint.x) / 2;
    const midY = (fromPoint.y + toPoint.y) / 2 - 18;
    const recencyAlpha = Math.max(0.25, 0.68 - trail.recencyIndex * 0.14);
    const arrowX = fromPoint.x + (toPoint.x - fromPoint.x) * 0.78;
    const arrowY = fromPoint.y + (toPoint.y - fromPoint.y) * 0.78;
    const arrowAngle = getArrowAngleDegrees(fromPoint.x, fromPoint.y, toPoint.x, toPoint.y);
    const existing = trailNodes.get(trail.id);

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

    const line = context.scene.add
      .line(0, 0, fromPoint.x, fromPoint.y, toPoint.x, toPoint.y, 0x38bdf8, 0.55)
      .setOrigin(0, 0)
      .setLineWidth(2, 2)
      .setDepth(14)
      .setAlpha(recencyAlpha);
    const arrow = context.scene.add
      .triangle(arrowX, arrowY, 0, 10, 7, -6, -7, -6, 0x7dd3fc, recencyAlpha)
      .setDepth(15)
      .setRotation(Phaser.Math.DegToRad(arrowAngle));
    const label = context.scene.add
      .text(midX, midY, `${trail.actorName} →`, {
        color: "#7dd3fc",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "10px",
      })
      .setOrigin(0.5)
      .setDepth(16)
      .setAlpha(recencyAlpha);

    const fadeTween = context.scene.tweens.add({
      targets: [line, arrow, label],
      alpha: { from: recencyAlpha, to: Math.max(0.12, recencyAlpha - 0.18) },
      duration: 1800 + trail.recencyIndex * 300,
      yoyo: true,
      repeat: -1,
      ease: "Sine.InOut",
    });

    trailNodes.set(trail.id, { line, arrow, label, fadeTween });
  }
}

export function syncBubbles(
  context: SceneSyncContext,
  bubbleNodes: Map<string, BubbleNode>,
  world: SceneWorld,
): void {
  const activeIds = new Set(world.bubbles.map((bubble) => bubble.id));
  const locationMap = new Map(world.locations.map((location) => [location.id, location]));
  const agentMap = new Map(world.agents.map((agent) => [agent.id, agent]));

  for (const [bubbleId, node] of bubbleNodes.entries()) {
    if (activeIds.has(bubbleId)) {
      continue;
    }
    node.floatTween?.stop();
    node.box.destroy();
    node.text.destroy();
    bubbleNodes.delete(bubbleId);
  }

  for (const bubble of world.bubbles) {
    const location = locationMap.get(bubble.locationId);
    if (!location) {
      continue;
    }

    const speakingAgent = bubble.speakerAgentId ? agentMap.get(bubble.speakerAgentId) : undefined;
    const anchorPoint = speakingAgent
      ? context.getAgentPosition(location, speakingAgent.slotIndex)
      : context.mapWorldToCanvas(location.x, location.y, world.locations);
    const bubbleX = Math.min(650, Math.max(150, anchorPoint.x));
    const bubbleY = Math.min(430, Math.max(72, anchorPoint.y - 54 - bubble.recencyIndex * 18));
    const textValue = `${bubble.speakerName}: ${bubble.text}`;
    const bubbleWidth = Math.min(150, Math.max(92, textValue.length * 5.8));
    const bubbleAlpha = Math.max(0.48, 0.92 - bubble.recencyIndex * 0.16);
    const existing = bubbleNodes.get(bubble.id);

    if (existing) {
      existing.box.setPosition(bubbleX, bubbleY);
      existing.box.setSize(bubbleWidth, 24);
      existing.box.setAlpha(bubbleAlpha);
      existing.text.setPosition(bubbleX, bubbleY);
      existing.text.setText(textValue);
      existing.text.setAlpha(bubbleAlpha);
      continue;
    }

    const box = context.scene.add
      .rectangle(bubbleX, bubbleY, bubbleWidth, 24, 0xf8fafc, bubbleAlpha)
      .setStrokeStyle(1, 0xcbd5e1, 0.9)
      .setDepth(30);
    const text = context.scene.add
      .text(bubbleX, bubbleY, textValue, {
        color: "#0f172a",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "10px",
      })
      .setOrigin(0.5)
      .setDepth(31)
      .setAlpha(bubbleAlpha);

    const floatTween = context.scene.tweens.add({
      targets: [box, text],
      y: `-=${8 + bubble.recencyIndex * 2}`,
      alpha: { from: bubbleAlpha, to: Math.max(0.22, bubbleAlpha - 0.28) },
      duration: 1400 + bubble.recencyIndex * 180,
      yoyo: true,
      repeat: -1,
      ease: "Sine.InOut",
    });

    bubbleNodes.set(bubble.id, { box, text, floatTween });
  }
}

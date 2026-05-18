import type * as Phaser from "phaser";

import { CANVAS_HEIGHT, CANVAS_WIDTH } from "./world-scene-style";
import type { AgentNode, LocationNode } from "./world-scene-sync";

export type TooltipNode = {
  box: Phaser.GameObjects.Rectangle;
  text: Phaser.GameObjects.Text;
};

export function refreshLocationHighlights(
  locationNodes: Map<string, LocationNode>,
  highlightedLocationId: string | null
): void {
  for (const [locationId, node] of locationNodes.entries()) {
    const isHighlighted = highlightedLocationId === locationId;
    if (isHighlighted) {
      node.body.setTint(0xf8fafc);
      node.body.setScale(1.06);
      node.label.setAlpha(1);
      node.badge.setAlpha(1);
    } else {
      node.body.clearTint();
      node.body.setScale(1);
      node.label.setAlpha(0);
      node.badge.setAlpha(0);
    }
    node.label.setScale(isHighlighted ? 1.05 : 1);
    node.badge.setScale(isHighlighted ? 1.05 : 1);
    node.glow.setAlpha(isHighlighted ? 0.34 : node.glow.alpha);
  }
}

export function refreshAgentHighlights(
  scene: Phaser.Scene,
  agentNodes: Map<string, AgentNode>,
  highlightedAgentId: string | null
): void {
  for (const [agentId, node] of agentNodes.entries()) {
    const isHighlighted = highlightedAgentId === agentId;
    node.pulseTween?.stop();
    if (isHighlighted) {
      node.body.setTint(0xfef08a);
      node.marker.setScale(1.08);
      node.label.setAlpha(1);
      node.label.setScale(1.08);
      node.pulseTween = scene.tweens.add({
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
      node.label.setAlpha(0);
      node.label.setScale(1);
      node.pulseTween = undefined;
    }
  }
}

export function focusCameraOnSelection(
  camera: Phaser.Cameras.Scene2D.Camera,
  locationNodes: Map<string, LocationNode>,
  agentNodes: Map<string, AgentNode>,
  highlightedLocationId: string | null,
  highlightedAgentId: string | null
): void {
  const targetAgentNode = highlightedAgentId ? agentNodes.get(highlightedAgentId) : undefined;
  if (targetAgentNode) {
    camera.pan(targetAgentNode.body.x, targetAgentNode.body.y, 320, "Sine.easeInOut", true);
    return;
  }

  const targetLocationNode = highlightedLocationId
    ? locationNodes.get(highlightedLocationId)
    : undefined;
  if (targetLocationNode) {
    camera.pan(targetLocationNode.body.x, targetLocationNode.body.y, 320, "Sine.easeInOut", true);
    return;
  }

  camera.pan(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, 320, "Sine.easeInOut", true);
}

export function showTooltip(tooltip: TooltipNode | null, x: number, y: number, text: string): void {
  if (!tooltip) {
    return;
  }

  const width = Math.min(220, Math.max(120, text.length * 7 + 18));
  tooltip.box.setPosition(x, y);
  tooltip.box.setSize(width, 30);
  tooltip.box.setVisible(true);
  tooltip.text.setPosition(x, y);
  tooltip.text.setText(text);
  tooltip.text.setVisible(true);
}

export function hideTooltip(tooltip: TooltipNode | null): void {
  if (!tooltip) {
    return;
  }
  tooltip.box.setVisible(false);
  tooltip.text.setVisible(false);
}

export function playTapFeedback(
  scene: Phaser.Scene,
  ...targets: Phaser.GameObjects.GameObject[]
): void {
  scene.tweens.add({
    targets,
    scale: { from: 1, to: 1.08 },
    duration: 110,
    yoyo: true,
    ease: "Quad.Out",
  });
}

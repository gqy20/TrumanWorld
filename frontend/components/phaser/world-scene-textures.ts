import * as Phaser from "phaser";

import type { SceneAgent, SceneLocation } from "@/lib/world-scene-adapter";

import {
  AGENT_TEXTURE_SIZE,
  BUILDING_TEXTURE_SIZE,
  GROUND_TEXTURE_SIZE,
  getAgentColor,
  getAgentTextureKey,
  getConfiguredAgentTextureKey,
  getConfiguredLocationTextureKey,
  getLocationColor,
} from "./world-scene-style";

export function createPixelTextures(scene: Phaser.Scene): void {
  if (!scene.textures.exists("pixel-ground")) {
    generateGroundTexture(scene, "pixel-ground", "default");
  }

  const statuses: SceneAgent["status"][] = ["idle", "moving", "talking", "working", "resting"];
  for (const preset of ["default", "student", "resident"]) {
    for (const status of statuses) {
      const key =
        preset === "default" ? getAgentTextureKey(status) : getConfiguredAgentTextureKey(preset, status);
      if (!scene.textures.exists(key)) {
        generateAgentTexture(scene, key, status, preset);
      }
    }
  }
}

export function ensureGroundTexture(scene: Phaser.Scene, groundPreset: string): string {
  const key = groundPreset === "default" ? "pixel-ground" : `pixel-ground-${groundPreset}`;
  if (!scene.textures.exists(key)) {
    generateGroundTexture(scene, key, groundPreset);
  }
  return key;
}

export function ensureLocationTexture(scene: Phaser.Scene, location: SceneLocation): void {
  const visualPreset = location.visual.visualPreset ?? location.locationType;
  const textureKey = getConfiguredLocationTextureKey(visualPreset, location.locationType);
  if (!scene.textures.exists(textureKey)) {
    generateBuildingTexture(scene, textureKey, location.locationType, visualPreset);
  }
}

export function ensureAgentTexture(scene: Phaser.Scene, agent: SceneAgent): void {
  const preset = agent.visual?.visualPreset ?? "default";
  const key = getConfiguredAgentTextureKey(preset, agent.status);
  if (!scene.textures.exists(key)) {
    generateAgentTexture(scene, key, agent.status, preset);
  }
}

export function generateGroundTexture(
  scene: Phaser.Scene,
  key: string,
  groundPreset: string,
): void {
  const graphics = scene.make.graphics({ x: 0, y: 0 }, false);

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

export function generateBuildingTexture(
  scene: Phaser.Scene,
  key: string,
  locationType: string,
  visualPreset: string,
): void {
  const graphics = scene.make.graphics({ x: 0, y: 0 }, false);
  const baseColor = getLocationColor(locationType);
  const roofColor = Phaser.Display.Color.IntegerToColor(baseColor).darken(20).color;
  const lightColor = Phaser.Display.Color.IntegerToColor(baseColor).lighten(25).color;
  const darkColor = Phaser.Display.Color.IntegerToColor(baseColor).darken(35).color;

  graphics.fillStyle(0x0b1220, 0.5);
  graphics.fillRect(3, 21, 18, 2);

  switch (visualPreset) {
    case "shop":
    case "cafe":
      graphics.fillStyle(roofColor, 1);
      graphics.fillRect(2, 4, 20, 5);
      graphics.fillStyle(baseColor, 1);
      graphics.fillRect(4, 9, 16, 11);
      graphics.fillStyle(darkColor, 1);
      graphics.fillRect(18, 10, 3, 10);
      graphics.fillStyle(0xf8fafc, 1);
      graphics.fillRect(4, 10, 16, 2);
      graphics.fillStyle(lightColor, 1);
      graphics.fillRect(6, 14, 4, 3);
      graphics.fillRect(13, 14, 4, 3);
      graphics.fillStyle(darkColor, 1);
      graphics.fillRect(10, 16, 4, 4);
      break;
    case "grove":
    case "park":
    case "quad":
      graphics.fillStyle(0x14532d, 1);
      graphics.fillRect(3, 19, 18, 3);
      graphics.fillStyle(0x22c55e, 1);
      graphics.fillRect(7, 7, 10, 10);
      graphics.fillRect(3, 11, 6, 6);
      graphics.fillRect(15, 10, 6, 7);
      graphics.fillStyle(0x166534, 1);
      graphics.fillRect(10, 16, 4, 2);
      graphics.fillStyle(0x854d0e, 1);
      graphics.fillRect(10, 18, 4, 3);
      break;
    case "tower":
    case "office":
      graphics.fillStyle(roofColor, 1);
      graphics.fillRect(5, 2, 14, 4);
      graphics.fillStyle(baseColor, 1);
      graphics.fillRect(5, 6, 14, 15);
      graphics.fillStyle(darkColor, 1);
      graphics.fillRect(17, 7, 3, 13);
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
      graphics.fillRect(3, 5, 18, 6);
      graphics.fillStyle(baseColor, 1);
      graphics.fillRect(5, 11, 14, 9);
      graphics.fillStyle(darkColor, 1);
      graphics.fillRect(17, 12, 3, 8);
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
      graphics.fillRect(2, 4, 20, 5);
      graphics.fillStyle(baseColor, 1);
      graphics.fillRect(4, 9, 16, 11);
      graphics.fillStyle(darkColor, 1);
      graphics.fillRect(19, 10, 2, 10);
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
      graphics.fillRect(4, 19, 16, 2);
      graphics.fillStyle(baseColor, 1);
      graphics.fillRect(6, 7, 12, 12);
      graphics.fillStyle(lightColor, 1);
      graphics.fillRect(10, 5, 4, 3);
      graphics.fillRect(9, 11, 6, 2);
      graphics.fillStyle(0xe2e8f0, 1);
      graphics.fillRect(10, 13, 4, 4);
      break;
    default:
      graphics.fillStyle(roofColor, 1);
      graphics.fillRect(3, 5, 18, 5);
      graphics.fillStyle(baseColor, 1);
      graphics.fillRect(5, 10, 14, 10);
      graphics.fillStyle(darkColor, 1);
      graphics.fillRect(17, 11, 3, 9);
      graphics.fillStyle(lightColor, 1);
      graphics.fillRect(8, 11, 3, 3);
      graphics.fillRect(13, 11, 3, 3);
      graphics.fillStyle(darkColor, 1);
      graphics.fillRect(10, 14, 4, 4);
      break;
  }

  graphics.lineStyle(1, 0xe2e8f0, 0.45);
  graphics.strokeRect(4, 9, 16, 11);
  graphics.generateTexture(key, BUILDING_TEXTURE_SIZE, BUILDING_TEXTURE_SIZE);
  graphics.destroy();
}

export function generateAgentTexture(
  scene: Phaser.Scene,
  key: string,
  status: SceneAgent["status"],
  visualPreset: string,
): void {
  const graphics = scene.make.graphics({ x: 0, y: 0 }, false);
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

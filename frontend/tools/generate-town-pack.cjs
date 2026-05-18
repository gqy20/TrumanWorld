/* eslint-disable @typescript-eslint/no-require-imports */
const { existsSync, mkdirSync, rmSync, writeFileSync } = require("node:fs");
const path = require("node:path");
const { execFileSync, spawnSync } = require("node:child_process");
const { deflateSync } = require("node:zlib");

const packId = "default-town";
const outDir = path.join(__dirname, "..", "public", "world-assets", packId);
const frameWidth = 128;
const frameHeight = 128;
const columns = 8;
const rows = 4;
const frameCount = 32;
const sheetWidth = frameWidth * columns;
const sheetHeight = frameHeight * rows;

const frames = {
  home: 0,
  cafe: 1,
  office: 2,
  library: 3,
  plaza: 4,
  park: 5,
  generic: 6,
  roadStraight: 7,
  roadCross: 8,
  roadBend: 9,
  tree: 10,
  lamp: 11,
  bench: 12,
  flowers: 13,
  shrub: 14,
  agentIdle: 16,
  agentMoving: 17,
  agentTalking: 18,
  agentWorking: 19,
  agentResting: 20,
};

const colors = {
  transparent: [0, 0, 0, 0],
  shadow: [24, 28, 42, 82],
  outline: [39, 54, 72, 255],
  roofRed: [168, 75, 82, 255],
  roofBlue: [73, 111, 157, 255],
  roofGreen: [75, 128, 88, 255],
  wallWarm: [235, 196, 139, 255],
  wallLight: [244, 224, 181, 255],
  wallCool: [176, 202, 224, 255],
  wallStone: [187, 182, 169, 255],
  glass: [105, 184, 209, 255],
  glassLight: [194, 238, 239, 255],
  door: [94, 70, 56, 255],
  grass: [68, 153, 93, 255],
  grassLight: [131, 204, 105, 255],
  path: [222, 196, 143, 255],
  pathLight: [246, 232, 190, 255],
  pathDark: [189, 151, 93, 255],
  plaza: [171, 187, 195, 255],
  wood: [126, 84, 55, 255],
  metal: [88, 104, 123, 255],
  flowerPink: [239, 105, 151, 255],
  flowerYellow: [250, 204, 88, 255],
  agentBody: [244, 135, 71, 255],
  agentBodyBlue: [65, 165, 211, 255],
  agentBodyGreen: [78, 190, 118, 255],
  agentBodyViolet: [156, 126, 225, 255],
  agentSkin: [252, 198, 156, 255],
  agentHair: [46, 42, 49, 255],
  white: [248, 250, 252, 255],
  dark: [20, 26, 38, 255],
  talk: [255, 235, 154, 255],
};

function createCanvas() {
  return new Uint8ClampedArray(sheetWidth * sheetHeight * 4);
}

function frameOrigin(index) {
  return [(index % columns) * frameWidth, Math.floor(index / columns) * frameHeight];
}

function blendPixel(pixels, x, y, color) {
  if (x < 0 || y < 0 || x >= sheetWidth || y >= sheetHeight) return;
  const i = (Math.floor(y) * sheetWidth + Math.floor(x)) * 4;
  const alpha = color[3] / 255;
  const inverse = 1 - alpha;
  pixels[i] = Math.round(color[0] * alpha + pixels[i] * inverse);
  pixels[i + 1] = Math.round(color[1] * alpha + pixels[i + 1] * inverse);
  pixels[i + 2] = Math.round(color[2] * alpha + pixels[i + 2] * inverse);
  pixels[i + 3] = Math.round(255 * (alpha + (pixels[i + 3] / 255) * inverse));
}

function rect(pixels, frame, x, y, width, height, color) {
  const [ox, oy] = frameOrigin(frame);
  for (let yy = Math.floor(y); yy < Math.ceil(y + height); yy += 1) {
    for (let xx = Math.floor(x); xx < Math.ceil(x + width); xx += 1) {
      blendPixel(pixels, ox + xx, oy + yy, color);
    }
  }
}

function ellipse(pixels, frame, cx, cy, rx, ry, color) {
  const [ox, oy] = frameOrigin(frame);
  for (let y = Math.floor(cy - ry); y <= Math.ceil(cy + ry); y += 1) {
    for (let x = Math.floor(cx - rx); x <= Math.ceil(cx + rx); x += 1) {
      const dx = (x + 0.5 - cx) / rx;
      const dy = (y + 0.5 - cy) / ry;
      if (dx * dx + dy * dy <= 1) blendPixel(pixels, ox + x, oy + y, color);
    }
  }
}

function diamond(pixels, frame, cx, cy, width, height, color) {
  const [ox, oy] = frameOrigin(frame);
  for (let y = Math.floor(cy - height / 2); y <= Math.ceil(cy + height / 2); y += 1) {
    for (let x = Math.floor(cx - width / 2); x <= Math.ceil(cx + width / 2); x += 1) {
      const dx = Math.abs(x + 0.5 - cx) / (width / 2);
      const dy = Math.abs(y + 0.5 - cy) / (height / 2);
      if (dx + dy <= 1) blendPixel(pixels, ox + x, oy + y, color);
    }
  }
}

function isoBlock(pixels, frame, x, y, width, depth, height, top, left, right) {
  diamond(pixels, frame, x, y, width, depth, top);
  for (let h = 0; h < height; h += 1) {
    diamond(pixels, frame, x, y + h, width, depth, h < height / 2 ? left : right);
  }
  diamond(pixels, frame, x, y, width, depth, top);
}

function drawHouse(pixels, frame, palette) {
  ellipse(pixels, frame, 64, 105, 42, 12, colors.shadow);
  isoBlock(pixels, frame, 64, 70, 54, 32, 30, palette.wallLight, palette.wallWarm, palette.wallWarm);
  diamond(pixels, frame, 64, 50, 72, 34, palette.roof);
  rect(pixels, frame, 57, 77, 12, 22, colors.door);
  rect(pixels, frame, 37, 74, 12, 10, colors.glass);
  rect(pixels, frame, 79, 74, 12, 10, colors.glass);
  rect(pixels, frame, 38, 75, 10, 2, colors.glassLight);
  rect(pixels, frame, 80, 75, 10, 2, colors.glassLight);
}

function drawCafe(pixels, frame) {
  ellipse(pixels, frame, 64, 105, 46, 12, colors.shadow);
  isoBlock(pixels, frame, 64, 70, 62, 34, 28, colors.wallLight, colors.wallWarm, colors.wallWarm);
  diamond(pixels, frame, 64, 49, 76, 34, colors.roofRed);
  rect(pixels, frame, 34, 73, 60, 9, [250, 245, 225, 255]);
  for (let x = 37; x <= 86; x += 12) rect(pixels, frame, x, 73, 6, 9, [226, 88, 87, 255]);
  rect(pixels, frame, 48, 84, 12, 12, colors.glass);
  rect(pixels, frame, 68, 83, 14, 18, colors.door);
  rect(pixels, frame, 49, 85, 10, 2, colors.glassLight);
}

function drawOffice(pixels, frame) {
  ellipse(pixels, frame, 64, 106, 40, 11, colors.shadow);
  isoBlock(pixels, frame, 64, 54, 54, 30, 50, colors.wallCool, [124, 158, 190, 255], [99, 134, 169, 255]);
  diamond(pixels, frame, 64, 35, 62, 28, colors.roofBlue);
  for (let y = 55; y < 92; y += 12) {
    for (let x = 45; x < 80; x += 14) rect(pixels, frame, x, y, 7, 6, colors.glassLight);
  }
  rect(pixels, frame, 59, 93, 12, 14, colors.door);
}

function drawLibrary(pixels, frame) {
  ellipse(pixels, frame, 64, 106, 46, 12, colors.shadow);
  isoBlock(pixels, frame, 64, 70, 68, 34, 30, colors.wallStone, [158, 148, 131, 255], [134, 126, 112, 255]);
  diamond(pixels, frame, 64, 50, 78, 32, colors.roofBlue);
  for (let x = 39; x <= 82; x += 14) rect(pixels, frame, x, 75, 6, 24, colors.wallLight);
  rect(pixels, frame, 58, 87, 14, 15, colors.door);
}

function drawPlaza(pixels, frame) {
  ellipse(pixels, frame, 64, 105, 50, 12, colors.shadow);
  diamond(pixels, frame, 64, 82, 82, 44, colors.plaza);
  diamond(pixels, frame, 64, 82, 54, 28, [193, 207, 211, 255]);
  rect(pixels, frame, 60, 51, 8, 34, colors.outline);
  ellipse(pixels, frame, 64, 48, 12, 8, colors.glass);
}

function drawPark(pixels, frame) {
  ellipse(pixels, frame, 64, 105, 48, 12, colors.shadow);
  diamond(pixels, frame, 64, 84, 86, 42, colors.grass);
  for (const [x, y] of [[42, 70], [62, 61], [82, 72], [58, 84]]) {
    rect(pixels, frame, x - 3, y + 7, 6, 15, colors.door);
    ellipse(pixels, frame, x, y, 15, 13, colors.grassLight);
    ellipse(pixels, frame, x - 5, y + 1, 10, 9, colors.grass);
  }
  diamond(pixels, frame, 64, 95, 46, 14, colors.path);
}

function drawAgent(pixels, frame, bodyColor, opts = {}) {
  const x = 64 + (opts.lean || 0);
  const y = 66 + (opts.bob || 0);
  ellipse(pixels, frame, 64, 108, 18, 5, colors.shadow);
  rect(pixels, frame, x - 9, y + 26, 18, 22, bodyColor);
  rect(pixels, frame, x - 7, y + 48, 6, 14, colors.dark);
  rect(pixels, frame, x + 1, y + 48, 6, 14, colors.dark);
  ellipse(pixels, frame, x, y + 14, 13, 12, colors.agentSkin);
  rect(pixels, frame, x - 11, y + 4, 22, 8, colors.agentHair);
  rect(pixels, frame, x - 5, y + 14, 3, 3, colors.dark);
  rect(pixels, frame, x + 4, y + 14, 3, 3, colors.dark);
  rect(pixels, frame, x - 3, y + 21, 7, 2, opts.talking ? colors.talk : colors.dark);
  if (opts.walk) {
    rect(pixels, frame, x - 14, y + 35, 5, 14, bodyColor);
    rect(pixels, frame, x + 9, y + 33, 5, 14, bodyColor);
  } else {
    rect(pixels, frame, x - 13, y + 34, 5, 13, bodyColor);
    rect(pixels, frame, x + 8, y + 34, 5, 13, bodyColor);
  }
  if (opts.working) rect(pixels, frame, x + 13, y + 31, 12, 8, colors.glassLight);
  if (opts.resting) rect(pixels, frame, x + 11, y + 5, 12, 5, colors.white);
}

function drawRoadStraight(pixels, frame) {
  diamond(pixels, frame, 64, 78, 96, 46, colors.pathDark);
  diamond(pixels, frame, 64, 75, 88, 38, colors.path);
  diamond(pixels, frame, 64, 75, 62, 24, colors.pathLight);
}

function drawRoadCross(pixels, frame) {
  drawRoadStraight(pixels, frame);
  diamond(pixels, frame, 64, 75, 40, 74, colors.path);
  diamond(pixels, frame, 64, 75, 26, 54, colors.pathLight);
  ellipse(pixels, frame, 64, 76, 14, 7, [255, 247, 214, 210]);
}

function drawRoadBend(pixels, frame) {
  diamond(pixels, frame, 64, 78, 88, 40, colors.pathDark);
  diamond(pixels, frame, 56, 76, 66, 32, colors.path);
  diamond(pixels, frame, 75, 83, 36, 46, colors.path);
  diamond(pixels, frame, 60, 75, 36, 16, colors.pathLight);
  diamond(pixels, frame, 77, 83, 18, 28, colors.pathLight);
}

function drawTree(pixels, frame) {
  ellipse(pixels, frame, 64, 108, 24, 7, colors.shadow);
  rect(pixels, frame, 59, 75, 10, 32, colors.wood);
  ellipse(pixels, frame, 62, 63, 24, 19, colors.grass);
  ellipse(pixels, frame, 78, 67, 20, 16, colors.grassLight);
  ellipse(pixels, frame, 49, 70, 18, 15, [52, 132, 82, 255]);
  ellipse(pixels, frame, 64, 51, 19, 16, [88, 177, 96, 255]);
}

function drawLamp(pixels, frame) {
  ellipse(pixels, frame, 64, 110, 12, 4, colors.shadow);
  rect(pixels, frame, 61, 61, 6, 49, colors.metal);
  rect(pixels, frame, 56, 58, 16, 6, colors.outline);
  ellipse(pixels, frame, 64, 54, 11, 10, colors.flowerYellow);
  ellipse(pixels, frame, 64, 54, 17, 14, [250, 204, 88, 70]);
}

function drawBench(pixels, frame) {
  ellipse(pixels, frame, 64, 104, 28, 6, colors.shadow);
  rect(pixels, frame, 38, 77, 52, 8, colors.wood);
  rect(pixels, frame, 36, 89, 56, 10, colors.wood);
  rect(pixels, frame, 43, 96, 5, 12, colors.metal);
  rect(pixels, frame, 80, 96, 5, 12, colors.metal);
}

function drawFlowers(pixels, frame) {
  ellipse(pixels, frame, 64, 104, 26, 7, colors.shadow);
  diamond(pixels, frame, 64, 93, 54, 24, colors.grass);
  for (const [x, y, color] of [
    [48, 89, colors.flowerPink],
    [57, 96, colors.flowerYellow],
    [68, 88, colors.flowerPink],
    [78, 96, colors.white],
  ]) {
    ellipse(pixels, frame, x, y, 4, 4, color);
  }
}

function drawShrub(pixels, frame) {
  ellipse(pixels, frame, 64, 106, 23, 6, colors.shadow);
  ellipse(pixels, frame, 55, 89, 14, 12, colors.grass);
  ellipse(pixels, frame, 68, 86, 17, 14, colors.grassLight);
  ellipse(pixels, frame, 79, 93, 12, 10, [52, 132, 82, 255]);
}

function drawAll(pixels) {
  drawHouse(pixels, frames.home, { wallLight: colors.wallLight, wallWarm: colors.wallWarm, roof: colors.roofRed });
  drawCafe(pixels, frames.cafe);
  drawOffice(pixels, frames.office);
  drawLibrary(pixels, frames.library);
  drawPlaza(pixels, frames.plaza);
  drawPark(pixels, frames.park);
  drawHouse(pixels, frames.generic, { wallLight: colors.wallCool, wallWarm: colors.wallStone, roof: colors.roofGreen });
  drawRoadStraight(pixels, frames.roadStraight);
  drawRoadCross(pixels, frames.roadCross);
  drawRoadBend(pixels, frames.roadBend);
  drawTree(pixels, frames.tree);
  drawLamp(pixels, frames.lamp);
  drawBench(pixels, frames.bench);
  drawFlowers(pixels, frames.flowers);
  drawShrub(pixels, frames.shrub);
  drawAgent(pixels, frames.agentIdle, colors.agentBody);
  drawAgent(pixels, frames.agentMoving, colors.agentBodyBlue, { walk: true, lean: -2 });
  drawAgent(pixels, frames.agentTalking, colors.agentBody, { talking: true, bob: -1 });
  drawAgent(pixels, frames.agentWorking, colors.agentBodyGreen, { working: true });
  drawAgent(pixels, frames.agentResting, colors.agentBodyViolet, { resting: true, bob: 2 });
}

function crc32(buffer) {
  let crc = ~0;
  for (const byte of buffer) {
    crc ^= byte;
    for (let i = 0; i < 8; i += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return ~crc >>> 0;
}

function pngChunk(type, data) {
  const typeBuffer = Buffer.from(type);
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 0);
  return Buffer.concat([length, typeBuffer, data, crc]);
}

function pngBuffer(pixels) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(sheetWidth, 0);
  ihdr.writeUInt32BE(sheetHeight, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  const stride = sheetWidth * 4;
  const raw = Buffer.alloc((stride + 1) * sheetHeight);
  for (let y = 0; y < sheetHeight; y += 1) {
    raw[y * (stride + 1)] = 0;
    Buffer.from(pixels.buffer, y * stride, stride).copy(raw, y * (stride + 1) + 1);
  }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", deflateSync(raw)),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
}

function writeManifest() {
  const manifest = {
    schemaVersion: 2,
    id: packId,
    displayName: "Default Town",
    description: "Generated isometric town sprites for TrumanWorld stage rendering.",
    render: { mode: "sheet", pixelated: false },
    sprite: {
      image: "spritesheet.webp",
      frameWidth,
      frameHeight,
      columns,
      rows,
      frameCount,
    },
    buildings: {
      home: { frame: frames.home, anchor: [0.5, 0.86] },
      cafe: { frame: frames.cafe, anchor: [0.5, 0.86] },
      office: { frame: frames.office, anchor: [0.5, 0.88] },
      library: { frame: frames.library, anchor: [0.5, 0.86] },
      plaza: { frame: frames.plaza, anchor: [0.5, 0.86] },
      park: { frame: frames.park, anchor: [0.5, 0.86] },
      generic: { frame: frames.generic, anchor: [0.5, 0.86] },
    },
    tiles: {
      roadStraight: { frame: frames.roadStraight, anchor: [0.5, 0.5], display: [78, 38] },
      roadCross: { frame: frames.roadCross, anchor: [0.5, 0.5], display: [78, 38] },
      roadBend: { frame: frames.roadBend, anchor: [0.5, 0.5], display: [78, 38] },
    },
    props: {
      tree: { frame: frames.tree, anchor: [0.5, 0.9], display: [54, 68] },
      lamp: { frame: frames.lamp, anchor: [0.5, 0.95], display: [28, 56] },
      bench: { frame: frames.bench, anchor: [0.5, 0.78], display: [48, 32] },
      flowers: { frame: frames.flowers, anchor: [0.5, 0.76], display: [36, 26] },
      shrub: { frame: frames.shrub, anchor: [0.5, 0.8], display: [40, 30] },
    },
    agents: {
      idle: [{ sprite: frames.agentIdle, duration: 800 }],
      moving: [
        { sprite: frames.agentMoving, duration: 140 },
        { sprite: frames.agentIdle, duration: 140 },
      ],
      talking: [
        { sprite: frames.agentTalking, duration: 220 },
        { sprite: frames.agentIdle, duration: 220 },
      ],
      working: [{ sprite: frames.agentWorking, duration: 260 }],
      resting: [{ sprite: frames.agentResting, duration: 900 }],
    },
  };
  writeFileSync(path.join(outDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
}

function convertPngToWebp(pngPath, webpPath) {
  if (commandExists("cwebp")) {
    execFileSync("cwebp", ["-quiet", "-q", "92", pngPath, "-o", webpPath], { stdio: "inherit" });
    return;
  }

  if (commandExists("ffmpeg")) {
    try {
      execFileSync("ffmpeg", [
        "-y",
        "-loglevel",
        "error",
        "-i",
        pngPath,
        "-c:v",
        "libwebp",
        "-quality",
        "92",
        "-compression_level",
        "6",
        webpPath,
      ], { stdio: "inherit" });
      return;
    } catch (error) {
      if (!commandExists("convert")) throw error;
    }
  }

  if (commandExists("convert")) {
    execFileSync("convert", [pngPath, "-quality", "92", webpPath], { stdio: "inherit" });
    return;
  }

  throw new Error("cannot generate WebP: install cwebp, ImageMagick convert, or ffmpeg with libwebp");
}

function commandExists(command) {
  const result = spawnSync("which", [command], { stdio: "ignore" });
  return result.status === 0;
}

mkdirSync(outDir, { recursive: true });
const pixels = createCanvas();
drawAll(pixels);
const tempPng = path.join(outDir, "spritesheet.tmp.png");
const webpPath = path.join(outDir, "spritesheet.webp");
writeFileSync(tempPng, pngBuffer(pixels));
convertPngToWebp(tempPng, webpPath);
if (existsSync(tempPng)) rmSync(tempPng);
writeManifest();
console.log(`generated ${packId}`);

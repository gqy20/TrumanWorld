import { chmod, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

class NodeFileReader {
  result = null;
  onloadend = null;

  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then((result) => {
      this.result = result;
      queueMicrotask(() => this.onloadend?.());
    });
  }

  readAsDataURL(blob) {
    blob.arrayBuffer().then((result) => {
      this.result = `data:${blob.type};base64,${Buffer.from(result).toString("base64")}`;
      queueMicrotask(() => this.onloadend?.());
    });
  }
}

globalThis.FileReader = NodeFileReader;

const PALETTE = {
  brick: 0xa45345,
  ember: 0xd86f45,
  ink: 0x172033,
  leaf: 0x7f9a68,
  limewash: 0xe7e7e1,
  moss: 0x667c5b,
  paving: 0xb9b4aa,
  slate: 0x526b7a,
  stone: 0xb9b4aa,
  wallCool: 0xc8d2d0,
  windowAmber: 0xf2b45b,
  wood: 0x76513e,
};

function coloredGeometry(geometry, color, transform = {}) {
  let copy = geometry.clone();
  if (copy.index) copy = copy.toNonIndexed();
  copy.deleteAttribute("uv");
  const { position = [0, 0, 0], rotation = [0, 0, 0], scale = [1, 1, 1] } = transform;
  copy.scale(...scale);
  copy.rotateX(rotation[0]);
  copy.rotateY(rotation[1]);
  copy.rotateZ(rotation[2]);
  copy.translate(...position);
  const rgb = new THREE.Color(color);
  const colors = new Float32Array(copy.attributes.position.count * 3);
  for (let index = 0; index < copy.attributes.position.count; index += 1) {
    colors[index * 3] = rgb.r;
    colors[index * 3 + 1] = rgb.g;
    colors[index * 3 + 2] = rgb.b;
  }
  copy.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  return copy;
}

function addFrontWindow(parts, glowParts, box, { x, y, z, width = 0.28, height = 0.24, frame = PALETTE.slate }) {
  parts.push(coloredGeometry(box, frame, {
    position: [x, y, z], scale: [width + 0.08, height + 0.08, 0.045],
  }));
  glowParts.push(coloredGeometry(box, PALETTE.windowAmber, {
    position: [x, y, z + 0.026], scale: [width, height, 0.03],
  }));
  parts.push(coloredGeometry(box, PALETTE.stone, {
    position: [x, y - height / 2 - 0.055, z + 0.04], scale: [width + 0.12, 0.055, 0.1],
  }));
}

function addSideWindow(parts, glowParts, box, { x, y, z, width = 0.28, height = 0.24, frame = PALETTE.slate }) {
  parts.push(coloredGeometry(box, frame, {
    position: [x, y, z], scale: [0.045, height + 0.08, width + 0.08],
  }));
  const direction = Math.sign(x) || 1;
  glowParts.push(coloredGeometry(box, PALETTE.windowAmber, {
    position: [x + direction * 0.026, y, z], scale: [0.03, height, width],
  }));
  parts.push(coloredGeometry(box, PALETTE.stone, {
    position: [x + direction * 0.04, y - height / 2 - 0.055, z], scale: [0.1, 0.055, width + 0.12],
  }));
}

function addDoorFrame(parts, box, { x, z, width = 0.3, height = 0.82 }) {
  parts.push(coloredGeometry(box, PALETTE.ink, {
    position: [x, height / 2 + 0.02, z], scale: [width + 0.09, height + 0.08, 0.045],
  }));
  parts.push(coloredGeometry(box, PALETTE.wood, {
    position: [x, height / 2 + 0.02, z + 0.027], scale: [width, height, 0.05],
  }));
}

function addEntranceCanopy(parts, box, { x, z, width = 0.62, color = PALETTE.slate }) {
  parts.push(coloredGeometry(box, color, {
    position: [x, 0.9, z], scale: [width, 0.08, 0.36],
  }));
  parts.push(coloredGeometry(box, PALETTE.stone, {
    position: [x, 0.075, z + 0.04], scale: [width + 0.12, 0.07, 0.34],
  }));
  for (const supportX of [x - width * 0.38, x + width * 0.38]) {
    parts.push(coloredGeometry(box, PALETTE.wood, {
      position: [supportX, 0.46, z + 0.12], scale: [0.055, 0.8, 0.055],
    }));
  }
}

function buildCafeCorner() {
  const root = new THREE.Group();
  root.name = "CafeCorner";
  root.userData = { assetId: "cafe.corner", forward: "+Z", unit: "meter" };
  const opaque = [];
  const windows = [];
  const box = new THREE.BoxGeometry(1, 1, 1);
  const cylinder = new THREE.CylinderGeometry(0.5, 0.5, 1, 12);
  const roof = new THREE.ConeGeometry(0.5, 0.56, 4);
  const foliage = new THREE.IcosahedronGeometry(0.5, 1);

  opaque.push(coloredGeometry(box, PALETTE.slate, { position: [0, 0.04, 0], scale: [1.66, 0.08, 1.56] }));
  opaque.push(coloredGeometry(box, PALETTE.limewash, { position: [0, 0.63, 0], scale: [1.5, 1.1, 1.4] }));
  opaque.push(coloredGeometry(box, PALETTE.stone, { position: [0, 1.17, 0], scale: [1.62, 0.08, 1.52] }));
  opaque.push(coloredGeometry(roof, PALETTE.brick, { position: [0, 1.36, 0], rotation: [0, Math.PI / 4, 0], scale: [1.76, 1, 1.66] }));
  addDoorFrame(opaque, box, { x: 0, z: 0.72 });
  opaque.push(coloredGeometry(box, PALETTE.paving, { position: [0, 0.07, 0.86], scale: [0.48, 0.06, 0.28] }));
  opaque.push(coloredGeometry(box, PALETTE.ink, { position: [0, 0.78, 0.765], scale: [1.34, 0.08, 0.04] }));
  opaque.push(coloredGeometry(box, PALETTE.limewash, { position: [0, 0.9, 0.86], scale: [1.3, 0.12, 0.34] }));
  for (const [index, x] of [-0.48, -0.16, 0.16, 0.48].entries()) {
    opaque.push(coloredGeometry(box, index % 2 === 0 ? PALETTE.brick : PALETTE.limewash, {
      position: [x, 0.9, 1.02], scale: [0.18, 0.12, 0.05],
    }));
  }
  opaque.push(coloredGeometry(box, PALETTE.brick, { position: [0.48, 1.42, 0.12], scale: [0.16, 0.48, 0.16] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [-0.56, 0.22, 0.98], scale: [0.42, 0.1, 0.42] }));
  opaque.push(coloredGeometry(cylinder, PALETTE.wood, { position: [-0.56, 0.48, 0.98], scale: [0.07, 0.5, 0.07] }));
  opaque.push(coloredGeometry(cylinder, PALETTE.wood, { position: [-0.76, 0.17, 0.98], scale: [0.08, 0.34, 0.08] }));
  opaque.push(coloredGeometry(cylinder, PALETTE.wood, { position: [-0.36, 0.17, 0.98], scale: [0.08, 0.34, 0.08] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [0.68, 0.25, 0.88], scale: [0.26, 0.2, 0.26] }));
  opaque.push(coloredGeometry(foliage, PALETTE.leaf, { position: [0.68, 0.46, 0.88], scale: [0.34, 0.28, 0.34] }));
  opaque.push(coloredGeometry(box, PALETTE.ember, { position: [0.7, 0.86, 0.765], scale: [0.26, 0.2, 0.04] }));

  for (const x of [-0.46, 0.46]) {
    addFrontWindow(opaque, windows, box, { x, y: 0.62, z: 0.735 });
  }
  addSideWindow(opaque, windows, box, { x: -0.765, y: 0.64, z: 0.1, width: 0.42, height: 0.32 });

  const shell = new THREE.Mesh(
    mergeGeometries(opaque, false),
    new THREE.MeshStandardMaterial({
      name: "CafeVertexPalette",
      vertexColors: true,
      roughness: 0.88,
      metalness: 0,
    }),
  );
  shell.name = "CafeShell";
  shell.castShadow = true;
  shell.receiveShadow = true;
  root.add(shell);
  root.add(buildWindowGlowMesh("CafeWindowGlow", windows));
  return root;
}

function buildHomeRow() {
  const root = new THREE.Group();
  root.name = "HomeRow";
  root.userData = { assetId: "home.row", forward: "+Z", unit: "meter" };
  const opaque = [];
  const windows = [];
  const box = new THREE.BoxGeometry(1, 1, 1);
  const cylinder = new THREE.CylinderGeometry(0.5, 0.5, 1, 12);
  const roof = new THREE.ConeGeometry(0.5, 0.56, 4);
  const foliage = new THREE.IcosahedronGeometry(0.5, 1);

  opaque.push(coloredGeometry(box, PALETTE.slate, { position: [0, 0.04, 0], scale: [1.64, 0.08, 1.54] }));
  opaque.push(coloredGeometry(box, PALETTE.limewash, { position: [-0.18, 0.62, 0], scale: [1.14, 1.08, 1.38] }));
  opaque.push(coloredGeometry(box, PALETTE.moss, { position: [0.5, 0.48, 0.08], scale: [0.34, 0.8, 1.16] }));
  opaque.push(coloredGeometry(box, PALETTE.stone, { position: [-0.18, 1.17, 0], scale: [1.28, 0.08, 1.5] }));
  opaque.push(coloredGeometry(box, PALETTE.brick, { position: [0.5, 0.89, 0.08], scale: [0.46, 0.07, 1.28] }));
  opaque.push(coloredGeometry(roof, PALETTE.slate, { position: [-0.18, 1.34, 0], rotation: [0, Math.PI / 4, 0], scale: [1.4, 1, 1.62] }));
  opaque.push(coloredGeometry(roof, PALETTE.brick, { position: [0.5, 1.06, 0.08], rotation: [0, Math.PI / 4, 0], scale: [0.54, 0.72, 1.38] }));
  opaque.push(coloredGeometry(box, PALETTE.brick, { position: [0.14, 1.4, -0.18], scale: [0.15, 0.5, 0.15] }));
  addDoorFrame(opaque, box, { x: 0.34, z: 0.7, width: 0.28 });
  opaque.push(coloredGeometry(box, PALETTE.paving, { position: [0.34, 0.07, 0.84], scale: [0.46, 0.06, 0.28] }));
  addFrontWindow(opaque, windows, box, { x: -0.42, y: 0.64, z: 0.705 });
  addFrontWindow(opaque, windows, box, { x: -0.05, y: 0.64, z: 0.705 });
  opaque.push(coloredGeometry(box, PALETTE.moss, { position: [-0.42, 0.64, 0.745], scale: [0.38, 0.04, 0.04] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [-0.43, 0.2, 0.87], scale: [0.5, 0.1, 0.18] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [-0.62, 0.13, 0.87], scale: [0.08, 0.26, 0.08] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [-0.24, 0.13, 0.87], scale: [0.08, 0.26, 0.08] }));
  opaque.push(coloredGeometry(cylinder, PALETTE.wood, { position: [0.7, 0.26, 0.62], scale: [0.22, 0.22, 0.22] }));
  opaque.push(coloredGeometry(foliage, PALETTE.leaf, { position: [0.7, 0.43, 0.62], scale: [0.34, 0.28, 0.34] }));

  root.add(buildVertexColorMesh("HomeShell", opaque));
  root.add(buildWindowGlowMesh("HomeWindowGlow", windows));
  return root;
}

function buildOfficeMidrise() {
  const root = new THREE.Group();
  root.name = "OfficeMidrise";
  root.userData = { assetId: "office.midrise", forward: "+Z", unit: "display-unit" };
  const opaque = [];
  const windows = [];
  const box = new THREE.BoxGeometry(1, 1, 1);
  const foliage = new THREE.IcosahedronGeometry(0.5, 1);

  opaque.push(coloredGeometry(box, PALETTE.slate, {
    position: [0, 0.04, 0], scale: [1.42, 0.08, 1.42],
  }));
  opaque.push(coloredGeometry(box, PALETTE.wallCool, {
    position: [0, 0.9, 0], scale: [1.28, 1.72, 1.28],
  }));
  opaque.push(coloredGeometry(box, PALETTE.moss, {
    position: [-0.52, 0.9, 0.655], scale: [0.14, 1.58, 0.08],
  }));
  opaque.push(coloredGeometry(box, PALETTE.slate, {
    position: [0, 1.78, 0], scale: [1.4, 0.16, 1.4],
  }));
  opaque.push(coloredGeometry(box, PALETTE.ink, {
    position: [0, 1.94, 0], scale: [0.76, 0.18, 0.76],
  }));
  opaque.push(coloredGeometry(box, PALETTE.slate, {
    position: [0, 2.06, 0], scale: [0.88, 0.08, 0.88],
  }));

  addDoorFrame(opaque, box, { x: 0.08, z: 0.655, width: 0.34, height: 0.84 });
  addEntranceCanopy(opaque, box, { x: 0.08, z: 0.82, width: 0.66 });
  for (const y of [0.76, 1.13, 1.5]) {
    for (const x of [-0.32, 0.38]) {
      addFrontWindow(opaque, windows, box, { x, y, z: 0.655, width: 0.24, height: 0.19 });
    }
    for (const z of [-0.31, 0.31]) {
      addSideWindow(opaque, windows, box, { x: 0.655, y, z, width: 0.24, height: 0.19 });
    }
  }

  opaque.push(coloredGeometry(box, PALETTE.wood, {
    position: [-0.46, 0.18, 0.82], scale: [0.34, 0.18, 0.24],
  }));
  opaque.push(coloredGeometry(foliage, PALETTE.leaf, {
    position: [-0.46, 0.34, 0.82], scale: [0.4, 0.24, 0.3],
  }));

  root.add(buildVertexColorMesh("OfficeShell", opaque));
  root.add(buildWindowGlowMesh("OfficeWindowGlow", windows));
  return root;
}

function buildClinicCorner() {
  const root = new THREE.Group();
  root.name = "ClinicCorner";
  root.userData = { assetId: "clinic.corner", forward: "+Z", unit: "display-unit" };
  const opaque = [];
  const windows = [];
  const box = new THREE.BoxGeometry(1, 1, 1);
  const cylinder = new THREE.CylinderGeometry(0.5, 0.5, 1, 12);
  const foliage = new THREE.IcosahedronGeometry(0.5, 1);

  opaque.push(coloredGeometry(box, PALETTE.slate, {
    position: [0, 0.04, 0], scale: [1.47, 0.08, 1.47],
  }));
  opaque.push(coloredGeometry(box, PALETTE.limewash, {
    position: [0, 0.7, 0], scale: [1.35, 1.32, 1.35],
  }));
  opaque.push(coloredGeometry(box, PALETTE.wallCool, {
    position: [-0.48, 0.56, 0.04], scale: [0.34, 1.02, 1.22],
  }));
  opaque.push(coloredGeometry(box, PALETTE.stone, {
    position: [0, 1.38, 0], scale: [1.47, 0.14, 1.47],
  }));
  opaque.push(coloredGeometry(box, PALETTE.slate, {
    position: [-0.3, 1.53, -0.18], scale: [0.5, 0.16, 0.54],
  }));
  opaque.push(coloredGeometry(cylinder, PALETTE.ink, {
    position: [0.42, 1.52, -0.24], scale: [0.16, 0.2, 0.16],
  }));

  addDoorFrame(opaque, box, { x: 0.28, z: 0.69, width: 0.34, height: 0.84 });
  addEntranceCanopy(opaque, box, { x: 0.28, z: 0.84, width: 0.62, color: PALETTE.brick });
  addFrontWindow(opaque, windows, box, {
    x: -0.35, y: 0.58, z: 0.69, width: 0.3, height: 0.24, frame: PALETTE.moss,
  });
  for (const z of [-0.34, 0.28]) {
    addSideWindow(opaque, windows, box, {
      x: 0.69, y: 0.7, z, width: 0.3, height: 0.24, frame: PALETTE.moss,
    });
  }

  opaque.push(coloredGeometry(box, PALETTE.brick, {
    position: [-0.35, 1.08, 0.704], scale: [0.42, 0.11, 0.055],
  }));
  opaque.push(coloredGeometry(box, PALETTE.brick, {
    position: [-0.35, 1.08, 0.704], scale: [0.11, 0.42, 0.055],
  }));
  opaque.push(coloredGeometry(box, PALETTE.wood, {
    position: [-0.58, 0.17, 0.82], scale: [0.28, 0.16, 0.22],
  }));
  opaque.push(coloredGeometry(foliage, PALETTE.leaf, {
    position: [-0.58, 0.31, 0.82], scale: [0.34, 0.22, 0.28],
  }));

  root.add(buildVertexColorMesh("ClinicShell", opaque));
  root.add(buildWindowGlowMesh("ClinicWindowGlow", windows));
  return root;
}

function buildParkOldOak() {
  const root = new THREE.Group();
  root.name = "ParkOldOak";
  root.userData = { assetId: "park.old-oak", forward: "+Z", unit: "meter" };
  const opaque = [];
  const box = new THREE.BoxGeometry(1, 1, 1);
  const cylinder = new THREE.CylinderGeometry(0.5, 0.5, 1, 12);
  const foliage = new THREE.IcosahedronGeometry(0.5, 1);

  opaque.push(coloredGeometry(cylinder, PALETTE.leaf, { position: [0, 0.025, 0], scale: [1.72, 0.05, 1.72] }));
  opaque.push(coloredGeometry(box, PALETTE.paving, { position: [0.22, 0.12, 0.1], rotation: [0, -0.38, 0], scale: [1.6, 0.05, 0.3] }));
  opaque.push(coloredGeometry(cylinder, PALETTE.wood, { position: [-0.34, 0.58, -0.18], scale: [0.3, 1.16, 0.3] }));
  opaque.push(coloredGeometry(cylinder, PALETTE.wood, { position: [-0.5, 1.02, -0.16], rotation: [0, 0, -0.62], scale: [0.16, 0.78, 0.16] }));
  opaque.push(coloredGeometry(cylinder, PALETTE.wood, { position: [-0.12, 1.08, -0.18], rotation: [0, 0, 0.58], scale: [0.15, 0.7, 0.15] }));
  opaque.push(coloredGeometry(foliage, PALETTE.moss, { position: [-0.42, 1.42, -0.18], scale: [1.04, 0.82, 1.04] }));
  opaque.push(coloredGeometry(foliage, PALETTE.leaf, { position: [-0.76, 1.34, -0.12], scale: [0.72, 0.64, 0.72] }));
  opaque.push(coloredGeometry(foliage, PALETTE.leaf, { position: [-0.06, 1.36, -0.26], scale: [0.78, 0.68, 0.78] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [0.48, 0.3, 0.42], rotation: [0, -0.38, 0], scale: [0.68, 0.12, 0.18] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [0.28, 0.17, 0.5], scale: [0.1, 0.34, 0.1] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [0.7, 0.17, 0.34], scale: [0.1, 0.34, 0.1] }));
  for (const [x, z, color] of [
    [0.62, -0.58, PALETTE.ember],
    [0.78, -0.42, PALETTE.windowAmber],
    [0.48, -0.4, PALETTE.limewash],
  ]) {
    opaque.push(coloredGeometry(foliage, color, { position: [x, 0.18, z], scale: [0.18, 0.18, 0.18] }));
  }

  root.add(buildVertexColorMesh("ParkShell", opaque));
  return root;
}

function buildVertexColorMesh(name, geometries) {
  const mesh = new THREE.Mesh(
    mergeGeometries(geometries, false),
    new THREE.MeshStandardMaterial({
      name: `${name}Palette`,
      vertexColors: true,
      roughness: 0.9,
      metalness: 0,
    }),
  );
  mesh.name = name;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function buildWindowGlowMesh(name, geometries) {
  const mesh = new THREE.Mesh(
    mergeGeometries(geometries, false),
    new THREE.MeshStandardMaterial({
      name: `${name}Palette`,
      color: 0xffffff,
      vertexColors: true,
      roughness: 0.34,
      metalness: 0.02,
      emissive: PALETTE.windowAmber,
      emissiveIntensity: 0.2,
    }),
  );
  mesh.name = name;
  mesh.castShadow = false;
  mesh.receiveShadow = false;
  return mesh;
}

async function exportGlb(object, relativePath) {
  const outputUrl = new URL(`../public/${relativePath}`, import.meta.url);
  await mkdir(new URL(".", outputUrl), { recursive: true });
  const result = await new GLTFExporter().parseAsync(object, {
    binary: true,
    onlyVisible: true,
  });
  const outputPath = fileURLToPath(outputUrl);
  await writeFile(outputPath, Buffer.from(result));
  await chmod(outputPath, 0o644);
  return { path: outputPath, bytes: result.byteLength };
}

const assets = [
  [buildCafeCorner(), "world/buildings/cafe-corner.glb"],
  [buildHomeRow(), "world/buildings/home-row.glb"],
  [buildOfficeMidrise(), "world/buildings/office-midrise.glb"],
  [buildClinicCorner(), "world/buildings/clinic-corner.glb"],
  [buildParkOldOak(), "world/vegetation/old-oak.glb"],
];
for (const [asset, relativePath] of assets) {
  const output = await exportGlb(asset, relativePath);
  console.log(`Generated ${output.path} (${output.bytes} bytes)`);
}

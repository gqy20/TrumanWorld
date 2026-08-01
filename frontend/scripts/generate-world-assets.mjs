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

function buildCafeCorner() {
  const root = new THREE.Group();
  root.name = "CafeCorner";
  root.userData = { assetId: "cafe.corner", forward: "+Z", unit: "meter" };
  const opaque = [];
  const box = new THREE.BoxGeometry(1, 1, 1);
  const cylinder = new THREE.CylinderGeometry(0.5, 0.5, 1, 8);
  const roof = new THREE.ConeGeometry(0.5, 0.56, 4);
  const foliage = new THREE.IcosahedronGeometry(0.5, 1);

  opaque.push(coloredGeometry(box, PALETTE.slate, { position: [0, 0.08, 0], scale: [1.66, 0.16, 1.56] }));
  opaque.push(coloredGeometry(box, PALETTE.limewash, { position: [0, 0.63, 0], scale: [1.5, 1.1, 1.4] }));
  opaque.push(coloredGeometry(roof, PALETTE.brick, { position: [0, 1.36, 0], rotation: [0, Math.PI / 4, 0], scale: [1.76, 1, 1.66] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [0, 0.38, 0.72], scale: [0.3, 0.6, 0.07] }));
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
    opaque.push(coloredGeometry(box, PALETTE.windowAmber, { position: [x, 0.62, 0.735], scale: [0.28, 0.24, 0.045] }));
  }
  opaque.push(coloredGeometry(box, PALETTE.windowAmber, { position: [-0.765, 0.64, 0.1], scale: [0.045, 0.32, 0.42] }));

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
  return root;
}

function buildHomeRow() {
  const root = new THREE.Group();
  root.name = "HomeRow";
  root.userData = { assetId: "home.row", forward: "+Z", unit: "meter" };
  const opaque = [];
  const box = new THREE.BoxGeometry(1, 1, 1);
  const cylinder = new THREE.CylinderGeometry(0.5, 0.5, 1, 8);
  const roof = new THREE.ConeGeometry(0.5, 0.56, 4);
  const foliage = new THREE.IcosahedronGeometry(0.5, 1);

  opaque.push(coloredGeometry(box, PALETTE.slate, { position: [0, 0.08, 0], scale: [1.64, 0.16, 1.54] }));
  opaque.push(coloredGeometry(box, PALETTE.limewash, { position: [-0.18, 0.62, 0], scale: [1.14, 1.08, 1.38] }));
  opaque.push(coloredGeometry(box, PALETTE.moss, { position: [0.5, 0.48, 0.08], scale: [0.34, 0.8, 1.16] }));
  opaque.push(coloredGeometry(roof, PALETTE.slate, { position: [-0.18, 1.34, 0], rotation: [0, Math.PI / 4, 0], scale: [1.4, 1, 1.62] }));
  opaque.push(coloredGeometry(roof, PALETTE.brick, { position: [0.5, 1.06, 0.08], rotation: [0, Math.PI / 4, 0], scale: [0.54, 0.72, 1.38] }));
  opaque.push(coloredGeometry(box, PALETTE.brick, { position: [0.14, 1.4, -0.18], scale: [0.15, 0.5, 0.15] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [0.34, 0.36, 0.7], scale: [0.28, 0.58, 0.07] }));
  opaque.push(coloredGeometry(box, PALETTE.windowAmber, { position: [-0.42, 0.64, 0.705], scale: [0.28, 0.24, 0.045] }));
  opaque.push(coloredGeometry(box, PALETTE.windowAmber, { position: [-0.05, 0.64, 0.705], scale: [0.28, 0.24, 0.045] }));
  opaque.push(coloredGeometry(box, PALETTE.moss, { position: [-0.42, 0.64, 0.745], scale: [0.38, 0.04, 0.04] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [-0.43, 0.2, 0.87], scale: [0.5, 0.1, 0.18] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [-0.62, 0.13, 0.87], scale: [0.08, 0.26, 0.08] }));
  opaque.push(coloredGeometry(box, PALETTE.wood, { position: [-0.24, 0.13, 0.87], scale: [0.08, 0.26, 0.08] }));
  opaque.push(coloredGeometry(cylinder, PALETTE.wood, { position: [0.7, 0.26, 0.62], scale: [0.22, 0.22, 0.22] }));
  opaque.push(coloredGeometry(foliage, PALETTE.leaf, { position: [0.7, 0.43, 0.62], scale: [0.34, 0.28, 0.34] }));

  root.add(buildVertexColorMesh("HomeShell", opaque));
  return root;
}

function buildParkOldOak() {
  const root = new THREE.Group();
  root.name = "ParkOldOak";
  root.userData = { assetId: "park.old-oak", forward: "+Z", unit: "meter" };
  const opaque = [];
  const box = new THREE.BoxGeometry(1, 1, 1);
  const cylinder = new THREE.CylinderGeometry(0.5, 0.5, 1, 8);
  const foliage = new THREE.IcosahedronGeometry(0.5, 1);

  opaque.push(coloredGeometry(cylinder, PALETTE.leaf, { position: [0, 0.05, 0], scale: [1.72, 0.1, 1.72] }));
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
  [buildParkOldOak(), "world/vegetation/old-oak.glb"],
];
for (const [asset, relativePath] of assets) {
  const output = await exportGlb(asset, relativePath);
  console.log(`Generated ${output.path} (${output.bytes} bytes)`);
}

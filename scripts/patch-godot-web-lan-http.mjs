#!/usr/bin/env node

import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const outputPath = process.argv[2];
if (!outputPath) throw new Error("Usage: patch-godot-web-lan-http.mjs <index.html>");

const htmlPath = resolve(outputPath);
let html = readFileSync(htmlPath, "utf8");

const configPattern = /const GODOT_CONFIG = (\{[^\n]+\});/;
const configMatch = html.match(configPattern);
if (!configMatch) throw new Error(`Godot config not found in ${htmlPath}`);

const config = JSON.parse(configMatch[1]);
config.args = Array.isArray(config.args) ? config.args : [];
if (!config.args.includes("--audio-driver")) {
  config.args.push("--audio-driver", "Dummy");
}
html = html.replace(configPattern, `const GODOT_CONFIG = ${JSON.stringify(config)};`);

const originalFeatureCheck = `\tconst missing = Engine.getMissingFeatures({
\t\tthreads: GODOT_THREADS_ENABLED,
\t});`;
const patchedFeatureCheck = `\t// TRUMANWORLD_LAN_HTTP: this no-thread, no-audio lab may run on private LAN HTTP.
\tconst missing = Engine.getMissingFeatures({
\t\tthreads: GODOT_THREADS_ENABLED,
\t}).filter((feature) => {
\t\tconst host = window.location.hostname;
\t\tconst privateLanHost = /^(10\\.|192\\.168\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|100\\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\\.)/.test(host)
\t\t\t|| /^(fc|fd)/i.test(host);
\t\tconst allowedLanHttp = window.location.protocol === 'http:'
\t\t\t&& !GODOT_THREADS_ENABLED
\t\t\t&& privateLanHost;
\t\treturn !(allowedLanHttp && feature.startsWith('Secure Context'));
\t});`;

if (!html.includes("TRUMANWORLD_LAN_HTTP")) {
  if (!html.includes(originalFeatureCheck)) {
    throw new Error(`Godot feature check changed; refusing to patch ${htmlPath}`);
  }
  html = html.replace(originalFeatureCheck, patchedFeatureCheck);
}

writeFileSync(htmlPath, html);
console.log(`Enabled private-LAN HTTP for the Godot no-thread build: ${htmlPath}`);

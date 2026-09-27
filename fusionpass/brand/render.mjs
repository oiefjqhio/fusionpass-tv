// Renders the Fusion Pass brand PNGs for the app from logo.svg + League Spartan.
//   node render.mjs  (needs playwright-core + a Chromium; outputs into ./out)
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
const here = path.dirname(new URL(import.meta.url).pathname);
const exe = process.env.CHROME || fs.readdirSync(`${process.env.HOME}/.cache/ms-playwright`).filter((d) => d.startsWith('chromium-')).map((d) => `${process.env.HOME}/.cache/ms-playwright/${d}/chrome-linux64/chrome`)[0];
const jobs = [
  ...[['mdpi', 48], ['hdpi', 72], ['xhdpi', 96], ['xxhdpi', 144], ['xxxhdpi', 192]].map(([d, s]) => [`ic_launcher-${d}.png`, 'icon', s, s]),
  ['banner-xhdpi.png', 'banner', 320, 180],
  ['tv_banner.png', 'banner', 1280, 720],
  ['app_logo_mark.png', 'mark', 1080, 1080],
  ['app_logo_wordmark.png', 'wordmark', 1085, 344],
  ['brand_text.png', 'text', 1000, 230],
];
const b = await chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--allow-file-access-from-files'] });
fs.mkdirSync(`${here}/out`, { recursive: true });
for (const [name, k, w, h] of jobs) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.goto(`file://${here}/render.html?k=${k}&w=${w}&h=${h}`);
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(150);
  await p.screenshot({ path: `${here}/out/${name}`, omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
  await p.close();
  console.log('rendered', name, `${w}x${h}`);
}
await b.close();

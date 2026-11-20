#!/usr/bin/env node
// 在三个固定位置给游戏截图（技能第 5 步"并排图"的素材来源）。
//
//   node tests/capture_spots.mjs
//
// 依赖 ?debug=1 暴露的 teleportToSurface（只用于测试，正常游玩没有这个口子）。
// 输出：games/pingchuan-rail/pairs/game_<spot>.png

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPOSITORY_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const GAME_PATH = '/games/pingchuan-rail/game/index.html';
const OUTPUT_DIRECTORY = path.join(REPOSITORY_ROOT, 'games', 'pingchuan-rail', 'pairs');

// 三个固定位置：站台、轨道、竖井（与 SPEC 第 4/9 节一致，每次都用这三处）
const SPOTS = [
  { name: 'station', surfaceIndex: 0, along: 31, note: '站台：灯下残骸' },
  { name: 'tunnel', surfaceIndex: 3, along: 120, note: '轨道：断口与纵深' },
  { name: 'shaft', surfaceIndex: 10, along: 15.6, note: '竖井：垂直与扫描锥' },
];

const MIME_TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.glb': 'model/gltf-binary', '.mp3': 'audio/mpeg' };

function startStaticServer() {
  const server = http.createServer((request, response) => {
    const requestedPath = decodeURIComponent((request.url || '/').split('?')[0]);
    const filePath = path.join(REPOSITORY_ROOT, requestedPath);
    if (!filePath.startsWith(REPOSITORY_ROOT) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      response.writeHead(404).end('not found');
      return;
    }
    response.writeHead(200, { 'Content-Type': MIME_TYPES[path.extname(filePath)] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port })));
}

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium',
  ].filter(Boolean);
  return candidates.find((candidate) => fs.existsSync(candidate));
}

async function main() {
  const { chromium } = await import('playwright-core');
  const chromePath = findChrome();
  if (!chromePath) { console.log('SKIP: 找不到 Chrome'); return 2; }
  fs.mkdirSync(OUTPUT_DIRECTORY, { recursive: true });

  const { server, port } = await startStaticServer();
  const browser = await chromium.launch({ executablePath: chromePath, headless: true,
    args: ['--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=default', '--mute-audio'] });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  page.on('console', (message) => { if (message.type() === 'error' && !message.text().includes('favicon')) errors.push(message.text()); });

  try {
    await page.goto(`http://127.0.0.1:${port}${GAME_PATH}?autostart&seed=7&debug=1`, { waitUntil: 'load', timeout: 60000 });
    await page.waitForFunction(() => window.__game && window.__game.debug, { timeout: 20000 });
    await page.waitForTimeout(2500);   // 等模型加载完
    for (const spot of SPOTS) {
      await page.evaluate(([index, along]) => {
        window.__game.debug.teleportToSurface(index, along);
      }, [spot.surfaceIndex, spot.along]);
      await page.waitForTimeout(1200);  // 等相机跟上
      const destination = path.join(OUTPUT_DIRECTORY, `game_${spot.name}.png`);
      await page.screenshot({ path: destination });
      console.log(`${spot.name}: ${spot.note} -> ${path.basename(destination)}`);
    }
  } finally {
    await browser.close();
    server.close();
  }
  console.log(errors.length ? `FAIL：${errors.length} 条控制台错误\n` + errors.slice(0, 3).join('\n') : 'PASS：三张截图完成，0 控制台错误');
  return errors.length ? 1 : 0;
}

process.exit(await main());
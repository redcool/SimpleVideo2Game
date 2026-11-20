#!/usr/bin/env node
// 原型冒烟测试：起一个静态服务、用系统 Chrome 打开游戏、按键、读 window.__game。
// 只验证"能不能跑、好不好操作"这类硬事实，不判断好不好看。
//
//   node tests/smoke_game.mjs
//   node tests/smoke_game.mjs --keep     # 保留浏览器窗口（默认 headless）
//
// 退出码：0 通过；1 失败；2 没有浏览器（跳过）。

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPOSITORY_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const GAME_PATH = '/games/pingchuan-rail/game/index.html';
const keepBrowser = process.argv.includes('--keep');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.glb': 'model/gltf-binary',
};

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
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
  ].filter(Boolean);
  return candidates.find((candidate) => fs.existsSync(candidate));
}

async function readState(page) {
  return page.evaluate(() => window.__game?.state ?? null);
}

async function waitForState(page, predicate, timeoutMilliseconds, description) {
  const deadline = Date.now() + timeoutMilliseconds;
  let lastState = null;
  while (Date.now() < deadline) {
    lastState = await readState(page);
    if (lastState && predicate(lastState)) return lastState;
    await page.waitForTimeout(60);
  }
  throw new Error(`等待超时：${description}（最后状态 ${JSON.stringify(lastState)}）`);
}

async function main() {
  let chromium;
  try {
    ({ chromium } = await import('playwright-core'));
  } catch {
    ({ chromium } = await import('playwright'));
  }

  const chromePath = findChrome();
  if (!chromePath) {
    console.log('SKIP: 找不到 Chrome，设置 CHROME_PATH 后再跑');
    return 2;
  }

  const { server, port } = await startStaticServer();
  const browser = await chromium.launch({
    executablePath: chromePath,
    headless: !keepBrowser,
    args: ['--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=default', '--mute-audio'],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const consoleErrors = [];
  page.on('pageerror', (error) => consoleErrors.push(String(error)));
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const text = message.text();
    if (text.includes('favicon')) return;   // 404 图标与游戏无关
    consoleErrors.push(text);
  });

  const failures = [];
  try {
    await page.goto(`http://127.0.0.1:${port}${GAME_PATH}?autostart&seed=7&debug=1`, { waitUntil: 'load', timeout: 60000 });
    await waitForState(page, (state) => state.phase === 'play', 20000, '进入 play 阶段');
    const initial = await readState(page);
    // 三个残骸 GLB 必须全部加载（少一个就说明素材路径或格式坏了）
    await waitForState(page, (state) => state.models_loaded === 3, 8000, '三个残骸模型加载');
    const withModels = await readState(page);
    if (withModels.models_failed > 0) failures.push('有模型加载失败：' + withModels.models_failed);
    console.log('初始状态：', JSON.stringify(initial));

    // 1) 向右爬，x 必须增加
    await page.keyboard.down('ArrowRight');
    await page.waitForTimeout(1500);
    await page.keyboard.up('ArrowRight');
    const afterCrawl = await readState(page);
    console.log('爬行后：', JSON.stringify(afterCrawl));
    if (!(afterCrawl.x > initial.x + 2)) failures.push(`爬行无效：x ${initial.x} -> ${afterCrawl.x}`);

    // 2) 蓄力弹射：松开后必须出现过 attached=false
    await page.keyboard.down('Space');
    await page.waitForTimeout(700);
    const charged = await readState(page);
    if (!(charged.charge > 0.5)) failures.push(`蓄力没有累积：charge=${charged.charge}`);
    await page.keyboard.up('Space');
    const airborne = await waitForState(page, (state) => state.attached === false, 1500, '弹射离地');
    console.log('弹射瞬间：', JSON.stringify(airborne));

    // 3) 最终要能落回某个表面（不能永远飞）
    const landed = await waitForState(page, (state) => state.attached === true, 4000, '重新落地');
    console.log('落地后：', JSON.stringify(landed));
    if (!(landed.x > afterCrawl.x + 2)) failures.push(`弹射没有前进：x ${afterCrawl.x} -> ${landed.x}`);

    // 4) 帧率与错误
    await page.waitForTimeout(1200);
    const final = await readState(page);
    if (final.fps < 30) failures.push(`帧率过低：${final.fps}`);
    if (consoleErrors.length > 0) failures.push(`控制台错误 ${consoleErrors.length} 条：${consoleErrors.slice(0, 3).join(' | ')}`);

    // 5) 关卡连通性：逐个路口验证拐角接续（用测试钩子把虫子放到路口前）
    const junctions = [
      { name: '钢轨三 → 穹顶地面（共线接续）', surfaceIndex: 4, along: 147, key: 'ArrowRight', hold: 1400, expect: '穹顶地面' },
      { name: '穹顶后壁 → 井口平台', surfaceIndex: 8, along: 13.0, key: 'ArrowUp', hold: 1400, expect: '井口平台' },
      { name: '井口平台 → 竖井壁A', surfaceIndex: 9, along: 199.4, key: 'ArrowRight', hold: 1200, expect: '竖井壁A' },
      { name: '竖井壁A → 横档一', surfaceIndex: 10, along: 16.4, key: 'ArrowUp', hold: 1200, expect: '横档一' },
      { name: '横档一 → 竖井壁B', surfaceIndex: 11, along: 203.5, key: 'ArrowRight', hold: 1200, expect: '竖井壁B' },
      { name: '竖井壁B → 横档二', surfaceIndex: 12, along: 22.4, key: 'ArrowUp', hold: 1200, expect: '横档二' },
      { name: '横档二 → 竖井壁C', surfaceIndex: 13, along: 207.5, key: 'ArrowRight', hold: 1200, expect: '竖井壁C' },
      { name: '竖井壁C → 井顶', surfaceIndex: 14, along: 25.4, key: 'ArrowUp', hold: 1200, expect: '井顶' },
    ];
    for (const junction of junctions) {
      await page.evaluate(([index, along]) => window.__game.debug.teleportToSurface(index, along),
        [junction.surfaceIndex, junction.along]);
      await page.waitForTimeout(120);
      await page.keyboard.down(junction.key);
      await page.waitForTimeout(junction.hold);
      await page.keyboard.up(junction.key);
      const state = await readState(page);
      const passed = state.surface === junction.expect;
      console.log(`${passed ? 'OK  ' : 'FAIL'} ${junction.name} → ${state.surface} (x=${state.x}, y=${state.y})`);
      if (!passed) failures.push(`路口不连通：${junction.name}，实际落在 ${state.surface}`);
    }

    // 6) 抵达终点：放到井顶西端，向右走到冷冻舱
    await page.evaluate(() => window.__game.debug.teleportToSurface(15, 210));
    await page.keyboard.down('ArrowRight');
    const ended = await waitForState(page, (state) => state.phase === 'end', 8000, '走到冷冻舱触发结局');
    await page.keyboard.up('ArrowRight');
    console.log('结局触发：', JSON.stringify(ended));

    console.log(`\n最终状态：${JSON.stringify(ended)}`);
    console.log(`控制台错误：${consoleErrors.length}`);
  } catch (error) {
    failures.push(String(error));
  } finally {
    await browser.close();
    server.close();
  }

  if (failures.length > 0) {
    console.log('FAIL');
    for (const failure of failures) console.log('  - ' + failure);
    return 1;
  }
  console.log('PASS：爬行 / 蓄力弹射 / 落地 / 帧率 都对');
  return 0;
}

process.exit(await main());
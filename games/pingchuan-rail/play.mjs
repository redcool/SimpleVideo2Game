// 试玩场景：一条蠕虫往前爬，遇到尽头/断口就蓄力弹射，竖井里往上爬。
// 只按键盘、只读 window.__game.state（绝不写游戏）。
export async function play(page, { seconds, t0 }) {
  const keyboard = page.keyboard;
  const state = () => page.evaluate(() => window.__game?.state);
  const end = t0 + seconds * 1000 - 200;

  await keyboard.press('Enter');            // 标题页 → 开始
  let lastAction = 0;
  let lastBite = 0;
  let lastAttached = true;

  while (Date.now() < end) {
    const snapshot = await state();
    if (!snapshot) break;

    // 竖井段（y > 13）改成往上爬，其余向右爬
    const climbing = snapshot.y > 13;
    await keyboard.down(climbing ? 'ArrowUp' : 'ArrowRight');

    // 每 0.4 秒咬一口：路上有巡逻怪，不咬会被打回去
    if (Date.now() - lastBite > 400) {
      await keyboard.press('j');
      lastBite = Date.now();
    }

    // 每 2.2 秒弹射一次：既跨断口，也让镜头里有动作
    if (Date.now() - lastAction > 2200) {
      await keyboard.up(climbing ? 'ArrowUp' : 'ArrowRight');
      await keyboard.down('Space');
      await page.waitForTimeout(650);
      await keyboard.up('Space');
      lastAction = Date.now();
    }

    // 掉出世界会自动重生，这里只记录状态变化，不干预
    if (lastAttached !== snapshot.attached) lastAttached = snapshot.attached;
    await page.waitForTimeout(70);
  }
  for (const key of ['ArrowUp', 'ArrowRight', 'ArrowLeft']) await keyboard.up(key);
}
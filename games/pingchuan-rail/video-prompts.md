# 参考视频提示词（等 GPU 空出来再跑）

用途：给 `workflows/h3_video.json`（待建）当输入。**一次只跑一条**，看完再决定下一条。
每条 10–15 s、1080p、16:9、侧视 3D、画面里不要任何 HUD 与文字。

为什么要 5 条：第 1 条验"站台能不能立住"，第 2 条验"速度感"，第 3 条验"机制读不读得出来"，
第 4 条验"垂直空间"，第 5 条验"终点有没有情绪"。**这 5 条不需要是同一条时间线**，
它们是 5 次"这张底片能不能复刻"的测试。

---

## 1. 站台（验空间与光）

> Side-view 3D game footage, cinematic realism. A small segmented worm crawls across a thick layer of
> grey-white dust on a ruined underground metro platform. Hundreds of destroyed wheeled and tracked
> combat robots lie on their sides, their torsos punched through by energy weapons, the torn metal rims
> cooled into a dark blue. A few ceiling fluorescent tubes still glow with a dying sickly green phosphor.
> Concrete pillars, cracked anti-slip tiles, heavy fog obscuring the far end. Slow lateral camera tracking
> at the worm's height. No text, no HUD, no characters.

要验证：粉尘是否读得出来、残骸是否成组而不杂乱、惨绿光是否足够当唯一光源。

## 2. 轨道（验速度感）

> Side-view 3D game footage. The same segmented worm races along rusted rails inside a flooded metro tunnel,
> body rippling over the ties, sparks spraying where a long steel-spined centipede drags itself across the
> rails far behind it. Dust and cold mist whip past the camera. Fast lateral tracking shot with motion blur
> on the foreground rails. Dark, desaturated, heavy fog, one sickly green light source far ahead.

要验证：横向速度能不能靠"前景模糊 + 粒子"立起来，而不靠镜头乱晃。

## 3. 弹射（验机制可读性）

> Side-view 3D game footage. The worm coils its segmented body into a tight spiral, the ring of small stones
> around its flattened head glinting, then launches itself across a broken gap in the track, tumbling in the
> air and landing on a rusted beam. Dust explodes from the launch point. Half-speed slow motion on the launch,
> then back to real time. Single cold light from above, everything else in grey fog.

要验证：不靠 UI，玩家能不能看懂"蓄力→弹射→落在金属上继续滑"。

## 4. 竖井（验垂直空间）

> Side-view 3D game footage. The worm climbs a vertical alloy-steel shaft, its body hugging the wall, climbing
> rungs receding into darkness above. Far above, a huge damaged prototype mech squats at the top of the shaft,
> its energy cannon melted and fused, a single sickly green scanning cone sweeping slowly down the shaft.
> The worm's skin glows faintly green. Camera tilts up as it climbs, dust drifting down past the lens.

要验证：竖井的高度感和"扫掠光"的压迫感是否成立（这决定终局关能不能做）。

## 5. 终点（验情绪）

> Side-view 3D game footage, quiet and still. The worm hangs at the edge of a small spherical chamber deep
> underground. In the centre of the chamber a tall cryogenic pod glows pale blue, a human silhouette suspended
> inside frosted glass-like solid. Concrete, rust, dust everywhere; the blue light is the only colour in the frame.
> Slow push-in, almost no motion. No text, no HUD.

要验证：一张"不解释的蓝光"能不能承担整个游戏的结尾。**这条最难，也最值得先看。**

---

## 跑完之后做什么

1. `python skills\video-to-game-local\scripts\study_video.py <clip>.mp4 -o games\pingchuan-rail\study\<n>`
2. 看 `sheet.jpg`，把能用的机位/配色抄进 `SPEC.md`（改数值要写一句为什么）。
3. `python skills\visual-taste\scripts\palette_report.py <clip>.mp4 --json > games\pingchuan-rail\study\<n>\palette.json`
   —— 这份 JSON 就是以后 `--baseline` 的参照。

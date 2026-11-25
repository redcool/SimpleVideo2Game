---
name: video-to-game-local
description: >-
  Turn a gameplay video into a real, playable Three.js game with every asset generated on
  this machine's ComfyUI (MiniMax H3 video, Z-Image/Qwen-Image stills, BiRefNet cutouts,
  Hunyuan3D meshes, Stable Audio / ACE-Step sound), then prove it with side-by-side frames
  of the video and the game and a recorded keyboard playtest. 本地版：素材全部由本机 ComfyUI
  生成，不调用任何付费 API。Use when the user wants an AI gameplay clip "turned into a game",
  "made playable", "recreated in the browser" or "rebuilt in Three.js/WebGL".
license: MIT
metadata:
  upstream: lovisdotio/video-to-game (MIT)
  localization: fal -> local ComfyUI
---

# Video to Game (local)

视频就是游戏的设计文档，而你看不到视频。视频模型擅长你差的那件事：一个游戏的**样子**、机位、一个记得住的机制。
你的活是把它反向工程成能玩的游戏，素材全部在本机 ComfyUI 现做，并且**用图片证明**，不要用形容词。

和上游的区别只有一处：第 3 步不再去 fal 买素材，而是提交本机 `workflows/*.json`。
代价从 6.5 USD/游戏变成 0，代价换来的是**时间**：每次生成都要等 GPU，所以更要"先想清楚再烧卡"。

## 工作流

1. **拿到视频。** 一个原创概念、一个看得见的机制、第三人称或侧视、画面里不要 HUD 文字。
   本机有 MiniMax H3 权重（`workflows/h3_video.json`，待建）；也可以用现成片段。
2. **研究它。** `python skills/video-to-game-local/scripts/study_video.py gameplay.mp4 -o games/<g>/study`
   出每 0.25 s 一帧、联络表、调色板、切点。先看 `sheet.jpg`，再看帧目录。
   **写 `SPEC.md` 再写代码**：机位（距离/高度/镜头）、主角、唯一机制、关键瞬间、世界布局、配色、光、材质、气质。
   见 `references/study-the-video.md`。
3. **在本机生成每一个素材**，一次一个任务，用视频自己的帧当参考图。图像优先用 **H3 image（本地，支持 4K，最准）**，
   需要文字/排版/局部精修时用 **MOSS**；Z-Image 只用来快速抽卡；真人也拍不出的高清定妆图才走云端 Ignis。
   `python skills/video-to-game-local/scripts/comfy_asset.py <workflow> -o games/<g>/assets --name <name> --set prompt="..." --seed 7`
   每个任务用哪个模型、参数怎么给，见 `references/local-assets.md`。
   **不许手画、不许下载图包、不许偷偷调云端**；每次生成都会写进 `assets/asset_log.json`。
4. **从 `skills/video-to-game-local/templates/game.html` 建游戏**：只有 Three.js + 一个 import map，真循环
   （控制、目标、推进、反馈、结束、重开），键盘 + 手柄，`?autostart`、`?seed=N`、`window.__game`。
   见 `references/game-loop.md`。
5. **对上样子。** 配色、雾、光、grade、bloom、暗角、颗粒是**规格**，不是最后的美化。
   每改一次就出并排图：
   `python skills/video-to-game-local/scripts/side_by_side.py gameplay.mp4 games/<g>/shot.png -o games/<g>/pairs --times 2,5,8`
   见 `references/look-and-post.md`。
5.5 **音频入库前先体检**：
   `python skills\audio-taste\scripts\audio_report.py assets\sfx_crawl.wav --profile sfx --strict`
   削顶、响度不在 −16 LUFS 附近、循环接缝断裂，这三类问题**必须修完再进游戏**。
6. **自己玩。** 写 `play.mjs`（照 `templates/play.mjs`）：只用键盘、只读 `window.__game.state`。
   `node skills/video-to-game-local/scripts/record_play.mjs "http://127.0.0.1:8000/?autostart" play.mjs -o take.mp4`
   按真实帧率录像；`python skills/video-to-game-local/scripts/best_window.py take.mp4 --length 10` 找最活的几秒。
   修复玩家会撞上的：掉下去、撞墙、死秒钟、看不清。见 `references/playtest.md`。
7. **交付**：`index.html` + `assets/` + `README.md`（概念、操作、每个素材来自哪个工作流）、
   并排图、最好的那段录像、以及**老实列出**和视频不一样的地方。

运行环境：本工程 `.venv`（`python`）+ ComfyUI 在 `http://127.0.0.1:8188` + ffmpeg + Node 18+ + Chrome。
开跑前先 `python skills/video-to-game-local/scripts/comfy_health.py`。

## 硬规则

- **游戏要像它的视频。** 同样的机位、配色、光、材质。每个"看起来对了"的判断都要落到并排图上，
  而且每次都在**同样三个位置**比。没有并排图 = 没检查过。
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
2. **研究它。** `python skill/scripts/study_video.py gameplay.mp4 -o games/<g>/study`
   出每 0.25 s 一帧、联络表、调色板、切点。先看 `sheet.jpg`，再看帧目录。
   **写 `SPEC.md` 再写代码**：机位（距离/高度/镜头）、主角、唯一机制、关键瞬间、世界布局、配色、光、材质、气质。
   见 `references/study-the-video.md`。
3. **在本机生成每一个素材**，一次一个任务，用视频自己的帧当参考图：
   `python skill/scripts/comfy_asset.py <workflow> -o games/<g>/assets --name <name> --set prompt="..." --seed 7`
   每个任务用哪个模型、参数怎么给，见 `references/local-assets.md`。
   **不许手画、不许下载图包、不许偷偷调云端**；每次生成都会写进 `assets/asset_log.json`。
4. **从 `skill/templates/game.html` 建游戏**：只有 Three.js + 一个 import map，真循环
   （控制、目标、推进、反馈、结束、重开），键盘 + 手柄，`?autostart`、`?seed=N`、`window.__game`。
   见 `references/game-loop.md`。
5. **对上样子。** 配色、雾、光、grade、bloom、暗角、颗粒是**规格**，不是最后的美化。
   每改一次就出并排图：
   `python skill/scripts/side_by_side.py gameplay.mp4 games/<g>/shot.png -o games/<g>/pairs --times 2,5,8`
   见 `references/look-and-post.md`。
6. **自己玩。** 写 `play.mjs`（照 `templates/play.mjs`）：只用键盘、只读 `window.__game.state`。
   `node skill/scripts/record_play.mjs "http://127.0.0.1:8000/?autostart" play.mjs -o take.mp4`
   按真实帧率录像；`python skill/scripts/best_window.py take.mp4 --length 10` 找最活的几秒。
   修复玩家会撞上的：掉下去、撞墙、死秒钟、看不清。见 `references/playtest.md`。
7. **交付**：`index.html` + `assets/` + `README.md`（概念、操作、每个素材来自哪个工作流）、
   并排图、最好的那段录像、以及**老实列出**和视频不一样的地方。

运行环境：本工程 `.venv`（`python`）+ ComfyUI 在 `http://127.0.0.1:8188` + ffmpeg + Node 18+ + Chrome。
开跑前先 `python skill/scripts/comfy_health.py`。

## 硬规则

- **游戏要像它的视频。** 同样的机位、配色、光、材质。每个"看起来对了"的判断都要落到并排图上，
  而且每次都在**同样三个位置**比。没有并排图 = 没检查过。
- **视频里的机制就是游戏。** 片段是"女孩把世界翻过来"，游戏就得是翻世界，不能是个换了模型的跑酷。
- **素材只来自本机 ComfyUI**，用视频的帧当参考。一个任务一次，看完结果再要下一个。
  seed 和工作流必须入库，别人（和明天的你）要能复现。
- **屏幕上不要文字**，除了一行最小标题和一行操作说明。世界自己会解释。
- **只要原创世界**：不用已有游戏/电影里的角色、logo、名字、关卡。
- **后处理是规格的一部分**：tone mapping、一个统一的 grade、bloom、雾（拉纵深）、暗角、颗粒。
  笔记本 60 fps；30 fps 只有在画面明显更好的时候才接受。
- **把世界安静下来。** 一套协调的调色，不要荧光色；密但要成组；主角和可交互物在安静的背景上要跳出来。
- **先玩再交付。** 一段零控制台错误的录像：不掉、没有死秒钟、视频里的关键瞬间在画面中间。
- **GPU 只归 ComfyUI。** 不要在 `.venv` 里装 torch（本机 5090 需要 cu130，见 README 的环境事实）。

## 参考怎么用

| 文件 | 什么时候读 |
|---|---|
| `references/study-the-video.md` | 开工：抽帧、调色板、机位、机制，要写的 SPEC |
| `references/local-assets.md` | 生成素材：任务 → 本机模型/节点 → 参数 → 显存与耗时 |
| `references/game-loop.md` | 写游戏：结构、输入、机位、状态契约、多人、性能 |
| `references/look-and-post.md` | 对上视频的样子：grade、雾、bloom、密度、层次、并排图流程 |
| `references/playtest.md` | 自己玩：场景、录像、best window、看完改什么 |

模板：`templates/game.html`（Three.js 骨架 + 后处理栈 + 输入 + 状态契约）、`templates/play.mjs`（键盘试玩场景）。

## 输出要说清楚

- 检查了什么、怎么检查的：哪几张并排图、哪段录像、多少 fps、控制台几个错误。
- 素材清单：每个素材来自哪个工作流、哪个 seed、跑了多久（`asset_log.json` 里现成的）。
- **老实**说和视频不一样的地方（简化了机制、少了个特效），永远不要写"完全一致"。

# NOTICE / 来源说明

## 上游

本工程的流水线方法和部分脚本改编自
[lovisdotio/video-to-game](https://github.com/lovisdotio/video-to-game)（MIT License，
Copyright (c) 2026 Lovis Odin）。

被改编的文件（保留了原始行为和 docstring 风格，改动点列在下面）：

| 本工程 | 上游 | 改动 |
|---|---|---|
| `skill/scripts/study_video.py` | `skills/video-to-game/scripts/study_video.py` | 复跑时清空旧的 `f_*.jpg`，帧表不再错位；其余一致 |
| `skill/scripts/side_by_side.py` | 同名 | 未改 |
| `skill/scripts/best_window.py` | 同名 | 未改 |
| `skill/scripts/record_play.mjs` | 同名 | 增加 Windows / `CHROME_PATH` 的浏览器探测；找不到浏览器时给出明确报错 |
| `skill/templates/game.html` | 同名 | 未改 |
| `skill/templates/play.mjs` | 同名 | 未改 |
| `skill/references/{study-the-video,game-loop,look-and-post,playtest}.md` | 同名 | 仅加来源注记；playtest 里的命令换成本工程路径 |
| `skill/SKILL.md` | 上游同名 | 第 3 步（素材生成）从 fal 换成本地 ComfyUI 产线 |

## 完全新增

- `skill/scripts/comfy_client.py`、`comfy_asset.py`、`comfy_health.py`：ComfyUI 资产桥
- `skill/references/local-assets.md`：本地模型 ↔ 上游 fal 端点的对照表
- `workflows/`、`tests/`、根目录文档

## 第三方服务与许可（运行时注意）

- 上游的素材规则是"一切都来自 fal"；本工程换成"一切都来自本机 ComfyUI"。
- UniMate 权重为 CC BY-NC 4.0（不可商用），训练数据受 Mixamo / Objaverse / Truebones 条款约束。
- Hunyuan3D 的权重与许可、Trellis2（MIT）等，商用前逐一确认。

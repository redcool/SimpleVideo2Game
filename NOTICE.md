# NOTICE / 来源说明

## 上游

本仓库的方法论与部分脚本改编自
[lovisdotio/video-to-game](https://github.com/lovisdotio/video-to-game)（MIT License，
Copyright (c) 2026 Lovis Odin）。

### skills/video-to-game-local/

| 本仓库 | 上游 | 改动 |
|---|---|---|
| `scripts/study_video.py` | `skills/video-to-game/scripts/study_video.py` | 复跑时清空旧的 `f_*.jpg`，帧表不再错位 |
| `scripts/record_play.mjs` | 同名 | 增加 Windows / `CHROME_PATH` 的浏览器探测；打印实际使用的浏览器 |
| `templates/game.html`、`templates/play.mjs` | 同名 | 未改 |
| `references/{study-the-video,game-loop,look-and-post,playtest}.md` | 同名 | 加来源注记；命令换成本仓库路径 |
| `SKILL.md` | 上游同名 | 第 3 步（素材生成）从 fal 换成本机 ComfyUI |
| `scripts/comfy_client.py`、`comfy_asset.py`、`comfy_health.py` | — | 本仓库新增 |
| `references/local-assets.md` | 替代上游 `fal-assets.md` | 本仓库新增：本地模型 ↔ 上游 fal 端点对照 |

### skills/visual-taste/

| 本仓库 | 上游 | 改动 |
|---|---|---|
| `scripts/side_by_side.py` | `scripts/side_by_side.py` | 行为一致；中文注释；变量名改为见名知意 |
| `scripts/rank_take_window.py` | `scripts/best_window.py` | 行为一致；中文注释；变量名改为见名知意 |
| `references/metrics.md`、`references/compare-routine.md` | 指标口径参考 `references/look-and-post.md` | 重新定义为可计算指标并给出阈值 |
| `scripts/palette_report.py`、`frame_metrics.py`、`visual_metrics_core.py`、`references/look-spec.md`、`tests/` | — | 本仓库新增 |

## 完全新增

`workflows/`、`tests/check_repo.py`、`tests/smoke_comfy.py`、`games/` 约定、根目录文档。

## 第三方服务与模型许可（运行时注意）

- 上游的素材规则是"一切都来自 fal"；本仓库换成"一切都来自本机 ComfyUI"，边际成本为 0。
- UniMate 权重为 CC BY-NC 4.0（不可商用）；训练数据受 Mixamo / Objaverse / Truebones 条款约束。
- Hunyuan3D、Trellis2（MIT）、Stable Audio、ACE-Step、TangoFlux、MiniMax 系列模型各有许可，
  商用前逐项确认。
- 适配器与技能代码：MIT（见 `LICENSE`）。

# AGENTS.md

本仓库是 **video2game-local**：把 gameplay 视频在本机复刻成 Three.js 游戏。
上游 `lovisdotio/video-to-game` 的方法论照用，素材生成从 fal 换成本机 ComfyUI。

## 目录

```text
skill/SKILL.md          7 步工作流与硬规则（要产出游戏时先读它）
skill/references/       选模型看 local-assets.md；写代码看 game-loop.md；验收看 look-and-post.md / playtest.md
skill/scripts/          comfy_health（环境自检）、comfy_asset（资产桥）、study_video、side_by_side、
                        best_window、record_play
skill/templates/        game.html（Three.js 骨架）、play.mjs（键盘试玩场景）
workflows/              ComfyUI 的 API 格式工作流；每个任务的入口
games/<game>/           study/（抽帧）assets/（素材 + asset_log.json）game/（代码）takes/（录像）pairs/（对比图）
tests/                  check_repo.py、smoke_comfy.py
```

## 命令

```powershell
.\.venv\Scripts\Activate.ps1
python skill\scripts\comfy_health.py                          # 产线自检
python tests\smoke_comfy.py                                    # 资产桥端到端
python tests\check_repo.py                                     # 静态检查（提交前必跑）
node --check skill\scripts\record_play.mjs                    # 录屏器语法
```

## 硬规则

- **解释器**：一律用本工程 `.venv`。**不要**在 venv 里装 torch —— 本机 GPU 只归 ComfyUI 的 Python。
- **Python 脚本**：3.11+，只用标准库（GUI 无关），`--help` 可读，docstring 里带用法示例；
  资产处理类才允许 `pillow` / `trimesh`（已在 requirements.txt）。
- **素材只从本机 ComfyUI 出**：不许手画、不许下载第三方图包、不许偷偷调云端 API。
  每次生成都必须经过 `comfy_asset.py`，让它写进 `assets/asset_log.json`（工作流、模型、seed、耗时、文件）。
- **可复现**：工作流文件必须带固定 seed 的能力（`--seed`），并入库；改工作流要说明理由。
- **Windows 优先**：路径用 `pathlib`，命令别假设 bash；`record_play.mjs` 必须能在本机 Chrome 上跑。
- **提交前**：`python tests/check_repo.py` 必须通过；不提交 `.venv/`、`_ref/`、视频、GLB、贴图。
- **注释与代码**：代码注释用英文；文档用中文。
- **不写绝对家目录**：任何提交文件里不出现 `C:\Users\…`、`H:\aiworks\…` 这类本机路径（配置走环境变量）。

## 加一个新游戏

`games/<name>/` 需要：`README.md`（概念、操作、素材清单、成本=0、与视频的差异）、
`game/index.html`（+ `assets/` 本地放，不入库）、`study/study.json`、`pairs/` 至少三张并排图、
`takes/` 一段录像。`tests/check_repo.py` 会检查这几项是否存在。

## 别做的事

- 不要改 `_ref/` 里的上游克隆（只读参考）。
- 不要把 ComfyUI 的模型目录搬进仓库。
- 不要为了"跑通"把 GPU 计算塞进 venv（装 torch 会立刻踩 sm_120 的坑）。

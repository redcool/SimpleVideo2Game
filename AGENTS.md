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

## 记忆系统使用(由 enroll.mjs 生成,0.0.16.13)
> 开始任务前:读本目录 `.brain.json` 取 token → 调用 hub(默认 127.0.0.1:45678,以部署实际为准)的 `memory.context`,**token 作为工具参数 `_brainToken` 传入**(不是 HTTP Bearer 头)。可先 `memory.whoami` 验证身份。不带 token = 访客,只看 studio 作用域,0 命中不代表没记忆。
> 会话结束(或用户说"存储记忆"):调 `memory.submit_session`,`session_id`=当前会话 id,`kind`="digest",`content`=本会话关键决定与新知识(400-1200 字,带出处,不含密钥)。
> 用户口令全表(存储记忆/获取记忆/查找记忆/记忆体检/登记记忆):<SimpleAIBrain>/docs/用户指令.md(部署约定:SimpleAIBrain 与 SimpleMcpServer 为同根兄弟目录;或设环境变量 SIMPLEAIBRAIN_HOME 指向 SimpleAIBrain 仓库)。
> 不要直接读记忆库数据文件当记忆来源——只有走工具才有正确的可见性与脱敏。
> 记忆之门 = hub(SimpleMcpServer,127.0.0.1:45678)。调用 memory.* 报 ECONNREFUSED/fetch failed = 门没开:向用户报告,由用户在**可见 cmd 窗口**启动 hub(启动与核对方法见 <SimpleAIBrain>/docs/用户指令.md(部署约定:SimpleAIBrain 与 SimpleMcpServer 为同根兄弟目录;或设环境变量 SIMPLEAIBRAIN_HOME 指向 SimpleAIBrain 仓库)「记忆之门」节);agent 不应私自后台拉起 hub。

## 记忆 project 标签(硬性,2026-10-24 确立)

- 本工作区所有 `memory.save` / `memory.submit_session` 调用,工具参数一律带 `project: "video2GamePrj"`(与 `_brainToken` 同级参数,非 HTTP 头)。
- 检索本项目记忆:`memory.context` / `memory.search` 带 `project: "video2GamePrj"`。
- 注:0.0.16.22 起 hub 会自动盖 project=agent_label(显式传参优先),此约定为显式保险。
- 无标签条目无法事后补标(`memory.edit` 不支持改 project 字段)。
- 背景:H:/ai_works/SimpleAIBrain/docs/project-tag-convention.md。

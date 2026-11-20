# AGENTS.md

本仓库是 **SimpleVideo2Game**：把 gameplay 视频在本机复刻成可玩的 Three.js 游戏。
素材全部由本机 ComfyUI 生成（MiniMax H3 / Z-Image / Hunyuan3D / Stable Audio），不调用付费 API。

## 一、协作纪律的来源（唯一的规则真源）

本仓库属于 **simple 品牌**，与其余子模块共用同一套协作纪律，规则**不在这里复制**：

- 规则仓库：<https://github.com/redcool/SimpleMcpServer>
- 本地副本（与本仓库同根、只读）：`../SimpleMcpServer/docsRules/`
  - `Agent工作纪律.md`：短句、不脑补先问、删除走 `.trash`、同名文件加版本号、夜班记录、版本号 x.y.z.w、
    `tmp/` 放临时文件、代码开发四问。
  - `Agent代码工程纪律.md`：模块化 + 单一职责 + 编排器、见名知意禁缩写、先读后写、最小修改、原子性、
    类型注解、结构化日志、中文注释、高危操作先批准、交付三段式。
  - `SimpleMCPServer搜索指南.md`：搜索结果是线索不是证据；多引擎顺序；来源分层；中文查询用 UTF-8 字节发送。

**规则与本地实践冲突时，以规则为准，并先问人。** 本文件只写"本仓库怎么落地这套规则"。

## 二、目录

```text
skills/                     可安装技能（每个技能一个目录，可整目录拷走）
  video-to-game-local/      本项目的技能：7 步工作流、素材产线、模板
    SKILL.md                入口：工作流 + 硬规则 + 参考路由
    references/             study-the-video / local-assets / game-loop / look-and-post / playtest
    scripts/                薄壳入口：comfy_health、comfy_asset、study_video、rank_take + record_play.mjs
    templates/              game.html（Three.js 骨架）、play.mjs（键盘试玩场景）
  audio-taste/              通用音频验收（响度/削顶/静音/循环接缝，与项目无关）
  visual-taste/             通用审美量化（与项目无关，可装进任何出图/出视频的库）
    SKILL.md                指标含义、阈值、四条工具、什么时候别用
    references/             metrics（定义/公式/校准）、look-spec（样子规格模板）、compare-routine
    scripts/                palette_report、frame_metrics、side_by_side、rank_take_window、visual_metrics_core
    tests/                  unittest（ffmpeg 合成图，不依赖 ComfyUI）
src/                       实现层（模块化，单一职责，中文注释）
  common/                  仓库路径探测、日志配置
  comfy_bridge/            HTTP、工作流、下载、记账、参考图落地、生成服务、自检
  video_study/             抽帧、联络表、主色、切点、研究编排
  playtest_capture/        录像最活窗口评分与切片
  pipeline_orchestrator/   唯一跨模块调度层（素材 / 研究 / 自检 / 试玩）
  command_line/            命令行入口（只解析参数）
workflows/                  ComfyUI 的 API 格式工作流，一个文件 = 一个素材任务
games/<game>/               study/ assets/ game/ takes/ pairs/ SPEC.md README.md
tests/                      check_repo.py（静态检查）、smoke_comfy.py（资产桥端到端）
tmp/                        临时文件、日志（不入库）
.trash/                     删除目标（不入库；不物理删除文件）
```

## 三、命令

```powershell
.\.venv\Scripts\Activate.ps1
$env:COMFY_HOME = "<ComfyUI portable 根目录>"                        # 需要参考图的工作流靠它找 input/
python skills\video-to-game-local\scripts\comfy_health.py           # 产线自检（缺什么一目了然）
python tests\smoke_comfy.py                                          # 资产桥端到端
python skills\video-to-game-local\scripts\rank_take.py take.mp4 --length 3   # 录像挑最活窗口
python skills\audio-taste\scripts\audio_report.py f.wav --profile sfx     # 音频体检（响度/削顶/接缝）
python -m unittest discover -s skills/visual-taste/tests -v          # 审美量化单测
python -m unittest discover -s skills/audio-taste/tests -v           # 音频量化单测
node tests\smoke_game.mjs                                            # 原型端到端（起服务 + Chrome 按键）
python tests\check_repo.py                                           # 静态检查（提交前必跑）
node --check skills\video-to-game-local\scripts\record_play.mjs     # 录屏器语法
```

## 四、硬规则（本仓库落地）

- **解释器**：一律用本仓库 `.venv`（Python 3.11）。**不要**在 venv 里装 torch：
  本机 RTX 5090 需要 cu130，GPU 计算只归 ComfyUI 自带的 Python。
- **素材只从本机 ComfyUI 出**：不手画、不下载图包、不偷偷调云端。每次生成都走 `comfy_asset.py`，
  由它写 `assets/asset_log.json`（工作流、模型、seed、耗时、文件）。参考图用 `--upload` 送进 `input/`，
  不要手工往 ComfyUI 目录里塞文件。
- **可复现**：工作流入库且能固定 seed；改工作流要在提交信息里说明理由。
- **代码风格**：中文注释说明"为什么"；函数带类型注解；变量名见名知意、禁缩写；
  CLI 结果用 print，诊断与进度用 logging；异常捕获写明具体类型，禁止空 `except`。
- **分层**：命令行走 `src/command_line`，只解析参数；跨模块调度只允许出现在
  `src/pipeline_orchestrator`；`skills/*/scripts/` 只放薄壳，不放实现。
- **生图优先级**：H3 image（本地 4K，首选）→ MOSS（排版/修图）→ Z-Image（抽卡）→ Qwen-Edit（改图）
  → Ignis gpt-image（云端积分，仅最后一公里）。
- **一个提交一件事**：改结构、改命名、加功能分开提交；测试未通过不许说"已完成"。
- **删除**：移动进 `.trash/`，不物理删除；同名文件不覆盖，加 `_v2` 之类的版本后缀。
- **不写本机绝对路径**：提交文件里不出现 `C:\Users\…`、`H:\aiworks\…`；配置走环境变量（见 `.env.example`）。
- **素材不上库**：视频、GLB、贴图、录音都在 `.gitignore` 之外，只提交代码、文档、工作流、日志。

## 五、加一个新游戏

`games/<name>/` 需要：`README.md`（概念、操作、素材清单、成本 0、与视频的差异）、`SPEC.md`（写代码之前写）、
`game/index.html`、`study/study.json`、`pairs/` 至少三张并排图、`takes/` 一段录像。
`python tests/check_repo.py` 会检查这几项。

## 六、记忆系统

本工作区已接入 simple 品牌的记忆之门（hub 由人在可见窗口启动，agent 不私自拉起）。

- 检索：`memory.context` / `memory.search`，参数带 `project: "video2GamePrj"`。
- 存档：会话结束或用户说"存储记忆"时调 `memory.submit_session`，`kind: "digest"`，
  同样带 `project: "video2GamePrj"`。
- 不把记忆库数据文件当记忆来源；只有走工具才有正确的可见性与脱敏。

## 七、别做的事

- 不要改 `_ref/`（上游克隆，只读参考）。
- 不要把 ComfyUI 的模型目录搬进仓库。
- 不要为了"跑通"把 GPU 计算塞进 venv。
- 不要在没有并排图和录像的情况下说"完成了"。
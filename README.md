# SimpleVideo2Game

把一段 gameplay 视频**在本机**复刻成可玩的 Three.js 浏览器游戏。
上游是 [lovisdotio/video-to-game](https://github.com/lovisdotio/video-to-game)（MIT，方法论完整、工程很薄）；
本仓库保留它的方法论，把"所有素材都去 fal 买"换成**本机 ComfyUI 产线**：
视频、图片、抠图、图生 3D、音效、音乐全部本地生成，边际成本 ≈ 0。

本仓库属于 **simple 品牌**，协作纪律见 <https://github.com/redcool/SimpleMcpServer>
（本机副本：`../SimpleMcpServer/docsRules/`）。`AGENTS.md` 只写"本仓库怎么落地这套规则"。

## 和上游的差别

| | 上游 | 本仓库 |
|---|---|---|
| 素材来源 | fal 平台，约 6.5 USD/游戏 | 本机 ComfyUI（`127.0.0.1:8188`），0 USD |
| 资产记账 | `fal_log.json` | `asset_log.json`（多记工作流 / 模型文件 / seed / 耗时） |
| 动作与绑定 | meshy rigging + animation（付费） | Mixamo 绑定 + 本机 UniMate 文本→动作 / GVHMR 视频动补 |
| 审美验收 | 形容词 + 眼睛 | `skills/visual-taste`：8 个可计算指标 + 并排图 + 与参考的差值 |

方法论那部分照抄不改：**视频即设计文档**、先写 SPEC 再写代码、每步用并排图验证、Agent 自己玩并录像。

## 结构

```text
skills/
  video-to-game-local/    本项目的技能（7 步工作流 + 素材产线 + 模板 + 薄壳入口）
  visual-taste/           通用审美量化技能（与项目无关，可整目录拷进任何库）
src/
  comfy_bridge/           ComfyUI 资产桥（HTTP、工作流、下载、记账、参考图、生成服务、自检）
  video_study/            抽帧、联络表、主色、切点
  playtest_capture/       录像最活窗口
  pipeline_orchestrator/  唯一跨模块调度层
  command_line/           命令行入口
workflows/                ComfyUI 的 API 格式工作流，一个文件 = 一个素材任务
games/<game>/             每个游戏的产物：SPEC.md、study/、assets/、game/、pairs/、takes/
tests/                    check_repo.py（静态检查）、smoke_comfy.py（资产桥端到端）
src/                      （M1 起放模块化实现；现在实现还在 skills/*/scripts/ 里）
tmp/  .trash/             临时文件 / 删除目标（都不入库）
```

## 快速开始

```powershell
cd <本仓库根目录>
.\.venv\Scripts\Activate.ps1                      # 之后所有 python 都是本仓库解释器
npm install                                       # 一次性：装 playwright-core（录屏器用）

# 1) 确认本机产线齐不齐（ComfyUI 通了才有输出）
python skills\video-to-game-local\scripts\comfy_health.py

# 2) 资产桥端到端（提交一个不烧 GPU 的工作流，确认能拿回文件）
python tests\smoke_comfy.py

# 3) 录像挑最活窗口 / 审美量化自测
python skills\video-to-game-local\scripts\rank_take.py take.mp4 --length 3
python -m unittest discover -s skills/visual-taste/tests -v

# 4) 研究视频：抽帧 + 联络表 + 调色板 + 切点
python skills\video-to-game-local\scripts\study_video.py games\demo\video\gameplay.mp4 -o games\demo\study

# 5) 量一张画面 / 和参考比差值
python skills\visual-taste\scripts\palette_report.py 参考帧.png --json > 参考.json
python skills\visual-taste\scripts\palette_report.py 成品帧.png --baseline 参考.json
```

ComfyUI 地址默认 `http://127.0.0.1:8188`，用环境变量 `COMFY_URL` 覆盖；其余配置见 `.env.example`。

## 参考视频从哪来

上游仓库里**没有原始 mp4**：`_ref/video-to-game` 只有 31 个 `poster.gif`（576×162、9 fps、20 帧、约 2.2 s，
且左右拼接了"视频 | 游戏"），只能当"长得像不像"的低保真参照，不能当设计文档。

所以参考动画有两条路：**用本机 H3 现生**（免费、可反复抽卡，这也是本项目的本意），或者你给一段
10–15 s、1080p、16:9、画面里没有 HUD 文字的 gameplay 片段。做 `h3_image_t2i` 这类素材工作流时不需要视频。

## 本机产线（已实测）

| 任务 | 本机实现 | 状态 |
|---|---|---|
| 视频生成 | **MiniMax H3 本地**（`workflows/h3_video.json`）：1152×640×124 帧、20 步、**带音轨**，150–190 s/条 | ✅ 已跑通（5 条参考片段已出） |
| 概念图 / 贴图 / 天空 / 视差层 | **H3 image**（本地 4K，✅ `workflows/h3_image_t2i.json`，3104² 常驻 11.2 s）、**MOSS**（本地打样/排版/指令修图，✅ `moss_t2i` + `moss_edit`，约 10–14 s）、Z-Image turbo（抽卡）、Qwen-Image-Edit 2511（改图）；云端 Ignis gpt-image2 兜底 | H3 image 可用，其余待接线 |
| 抠图 | **ComfyUI 核心内置** `LoadBackgroundRemovalModel` + `RemoveBackground`（BiRefNet 权重在位） | ✅ `workflows/birefnet_cutout.json`，实测 1.0 s/张 |
| 图生 3D | Hunyuan3D v2.1（核心节点）、Trellis2（核心节点） | 模型 + 节点就位，待建工作流 |
| 音效 / 音乐 | TangoFlux、Stable Audio Open、ACE-Step 1.5、MiniMax Music 3、YuE2 | 权重就位，待建工作流 |
| 绑定 | Mixamo（免费自动绑定） | 需手工一次，产出 rig 复用 |
| 动作 | 本机 UniMate（文本→动作）+ 循环化；GVHMR 视频动补 | 独立工程，见 `$env:AIGEN_ANIM_PRJ` |
| 录屏 / 对比 | `record_play.mjs`（已修 Windows）、`side_by_side.py`、`rank_take_window.py` | 可用（实测 60.5 fps 出片） |
| 资产桥 | `comfy_asset.py` → ComfyUI `/prompt` → 下载 + 记账 | 可用（冒烟已过） |
| 审美量化 | `palette_report`、`frame_metrics`、`side_by_side`、`rank_take_window` | 可用（8 个单测通过） |

## 阶段

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | 工程骨架、venv、资产桥、脚本迁移、Windows 录屏修复 | ✅ |
| M0.5 | `skills/` 布局归位、通用审美技能 `visual-taste`、纪律对齐、抠图工作流落地 | ✅ |
| M1 | `src/` 模块化重构（编排器 + 中文注释 + 类型注解） | ✅ |
| M1.5 | 素材工作流：`h3_image_t2i` ✅、`moss_edit`、`hunyuan3d_i23d`、`tangoflux_sfx`、`minimax_music3`、`h3_video` | 🚧 |
| M2 | 绑定→UniMate→GLB 动作链（角色能跑能跳） | ⏳ |
| M3 | 第一个完整游戏（照 SKILL.md 七步走通） | ⏳ |

版本号规则 `x.y.z.w`（x.y 由人定，z.w 由 agent 维护），当前见 `VERSION`。

## 环境事实（别踩）

- 本机主 Python（`D:\Program Files\Python311`）的 `torch 2.6.0+cu124` **跑不了 RTX 5090**（arch 只到 sm_90）。
  本仓库 venv 故意不装 torch；所有 GPU 计算走 ComfyUI 自带的 Python 3.13 + torch 2.13+cu130。
- ComfyUI 的模型目录很大（约 360 GB），路径放 `$env:COMFY_HOME`，不要复制进本仓库。
- 提交前必跑：`python tests/check_repo.py` 与 `python -m unittest discover -s skills/visual-taste/tests`。
- 跑需要参考图的工作流前，先设 `$env:COMFY_HOME`（ComfyUI portable 根目录），`--upload` 才能把图送进 `input/`。

## 许可

代码 MIT（见 `LICENSE`）。改编自上游的部分见 `NOTICE.md`。
运行时用到的模型各有许可，商用前逐项确认（UniMate 权重是 CC BY-NC 4.0，不可商用）。
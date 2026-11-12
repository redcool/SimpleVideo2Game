# video2game-local

把一段 gameplay 视频**在本机**复刻成可玩的 Three.js 浏览器游戏。上游是
[lovisdotio/video-to-game](https://github.com/lovisdotio/video-to-game)（MIT，方法论完整、工程很薄）；
本工程保留它的方法论，把"所有素材都去 fal 买"这一步换成**本机 ComfyUI 产线**：视频、图片、抠图、
图生 3D、音效、音乐全部本地生成，边际成本 ≈ 0。

## 和上游的三点差别

| | 上游 | 本工程 |
|---|---|---|
| 素材来源 | fal 平台，`fal_asset.py`，约 6.5 USD/游戏 | 本机 ComfyUI（127.0.0.1:8188），`comfy_asset.py`，0 USD |
| 资产记账 | `fal_log.json` | `asset_log.json`（多记 workflow / 模型文件 / seed / 耗时） |
| 动作与绑定 | meshy rigging + animation（付费） | Mixamo 绑定 + 本机 UniMate 文本→动作 / GVHMR 视频动补 |

方法论那部分照抄不改：**视频即设计文档**、先写 SPEC 再写代码、每一步用并排图验证、Agent 自己玩并录像。

## 结构

```text
video2GamePrj/
├── .venv/                    本工程解释器（Python 3.11，只装资产处理库，不装 torch）
├── skill/                    可安装的 skill（对齐上游结构，便于迁移到 ~/.agents/skills/）
│   ├── SKILL.md              7 步工作流 + 硬规则
│   ├── references/           study-the-video / local-assets / game-loop / look-and-post / playtest
│   ├── scripts/              study_video, best_window, side_by_side, record_play,
│   │                         comfy_health, comfy_asset, comfy_client
│   └── templates/            game.html（Three.js 骨架 + 后处理栈 + 状态契约）, play.mjs
├── workflows/                ComfyUI 的 API 格式工作流（Z-Image / Hunyuan3D / H3 / 音频 …）
├── games/<game>/             每个游戏的产物（study/ assets/ game/ takes/ pairs/ README.md）
├── tests/                    check_repo.py（静态检查）、smoke_comfy.py（资产桥端到端自检）
└── _ref/                     上游克隆，只读参考（不入库）
```

## 快速开始

```powershell
cd <本仓库根目录>
.\.venv\Scripts\Activate.ps1                      # 之后所有 python 都是本工程解释器

# 1) 确认本机产线齐不齐（ComfyUI 通了才有输出）
python skill\scripts\comfy_health.py

# 2) 资产桥端到端自检：提交一个不烧 GPU 的工作流，确认能拿回文件
python tests\smoke_comfy.py

# 3) 研究视频：抽帧 + 联络表 + 调色板 + 切点
python skill\scripts\study_video.py games\demo\video\gameplay.mp4 -o games\demo\study

# 4) 生成一个素材（工作流见 workflows/README.md）
python skill\scripts\comfy_asset.py workflows\smoke_empty_image.json -o games\demo\assets --name smoke
```

ComfyUI 地址默认 `http://127.0.0.1:8188`，用环境变量 `COMFY_URL` 覆盖。

## 本机产线（已实测）

| 任务 | 本机实现 | 状态 |
|---|---|---|
| 视频生成 | MiniMax H3 本地权重（`minimax_h3_fl2va/ref2va` int8）+ H3 Easy/Director 节点 | 权重与节点就位，待建工作流 |
| 概念图 / 贴图 / 天空 / 视差层 | Z-Image turbo、Qwen-Image-Edit 2511、Krea2 turbo、Ideogram4 | 权重就位，待建工作流 |
| 抠图 | BiRefNet / RMBG | 模型就位，待建工作流 |
| 图生 3D | Hunyuan3D v2.1（核心节点 `nodes_hunyuan3d`）、Trellis2（`nodes_trellis2`） | 模型 + 核心节点就位，待建工作流 |
| 音效 / 音乐 | Stable Audio Open、ACE-Step 1.5、MiniMax Music 3、TangoFlux、YuE2 | 权重就位，待建工作流 |
| 绑定 | Mixamo（免费自动绑定） | 需手工一次，产出 rig 复用 |
| 动作 | 本机 UniMate（文本→动作）+ 循环化；GVHMR 视频动补 | 独立工程，路径放 `$env:AIGEN_ANIM_PRJ`（默认同级目录 `../motionPrj/AIGenAnimPrj`） |
| 录屏 / 对比 | `record_play.mjs`（已修 Windows）、`side_by_side.py`、`best_window.py` | 可用 |
| 资产桥 | `comfy_asset.py` → ComfyUI `/prompt` → 下载 + 记账 | 可用（冒烟已过） |

## 阶段

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | 工程骨架、venv、资产桥、脚本迁移与 Windows 修复 | ✅ |
| M1 | 五个基础工作流：Z-Image 文生图、BiRefNet 抠图、Hunyuan3D 图生 3D、Stable Audio 音效、H3 视频 | ⏳ |
| M2 | 绑定→UniMate→GLB 的动作链（角色能跑能跳） | ⏳ |
| M3 | 第一个完整游戏（照 SKILL.md 七步走通） | ⏳ |

## 环境事实（别踩）

- 本机主 Python（`D:\Program Files\Python311`）的 `torch 2.6.0+cu124` **跑不了 RTX 5090**（arch 只到 sm_90）。
  本工程 venv 故意不装 torch；所有 GPU 计算走 ComfyUI 自带的 Python 3.13 + torch 2.13+cu130。
- ComfyUI 的模型目录很大（本机约 360 GB，路径放 `$env:COMFY_HOME`），不要复制进本工程。
- 本工程仓库只存代码、文档、工作流和小图；视频 / GLB / 贴图 / 录音都在 `.gitignore` 外。

## 许可

代码 MIT（见 `LICENSE`）。改编自上游的部分见 `NOTICE.md`。运行时用到的模型各有许可，
商用前请逐项确认（UniMate 权重是 CC BY-NC 4.0，不可商用）。
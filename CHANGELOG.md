# CHANGELOG

版本号规则 `x.y.z.w`：x（世代）、y（大版本）由人决定；z（大功能）、w（小改动）由 agent 维护。

**判定：z 只在该版本的功能清单全部完成（并有验证）时才升；未完结期间一律升 w。**
0.0.1 的功能清单（M0 骨架 → M1 工作流 → M2 动作链 → M3 首个游戏）尚未完结，
所以本次从 0.0.1.1 升到 **0.0.1.2**，不升 z。

## 0.0.1.4 — H3 生图探路 + 失败可读化（当前）

### 探路结论（写进 references/local-assets.md，避免重复踩坑）

ComfyUI 自带官方模板 `image_p_h3_t2i.json` 揭示了 p-h3-image 的真实配方：
**MiniMax H3 fl2va + p-h3-image LoRA + p-h3-image 专用 text_encoder / vae**，
经 `PH3ImageConditioning` 输出"视频 + 两条音频"的嵌套 latent，必须用 `SamplerCustomAdvanced`
配 `er_sde` 与模板给出的 9 段 sigmas。

本机缺三件官方资产（合计约 9.5 GB）：`p-h3-image_lora_bf16`、`p-h3-image_text_encoder_int8_convrot`、
`p-h3-image_vae_int8_convrot`（<https://huggingface.co/PrunaAI/p-h3-image-comfy>）。
用本机已有的 `minimax_h3_image_pruned_w4a8` 替代时，三种组合均失败，最后一次报
`节点 10（SamplerCustomAdvanced）IndexError: tuple index out of range`——
嵌套 AV latent 不被这条替代模型支撑。`workflows/h3_image_t2i.json` 保留为按官方模板写好的骨架，等资产到位。

### 改进

- 任务失败信息改成人话：`job_waiter.describe_failure` 只取 execution_error 的节点 id / 类型 / 异常首行，
  不再把整段 history 事件流倒进报错。
- README 增加"参考视频从哪来"：上游仓库 0 个 mp4，只有 576×162 / 9 fps / 2.2 s 的拼接 GIF，
  真参考只能本机 H3 现生或由人提供。

## 0.0.1.3 — src/ 模块化重构

### 结构

- 新增 `src/` 实现层，按模块分目录：`common`（仓库路径、日志）、`comfy_bridge`（HTTP、工作流、下载、记账、
  参考图落地、生成服务、自检）、`video_study`（抽帧/联络表/主色/切点）、`playtest_capture`（最活窗口）、
  `pipeline_orchestrator`（唯一跨模块调度）、`command_line`（只解析参数）。
- `skills/*/scripts/` 退化为薄壳入口（`comfy_asset`、`comfy_health`、`study_video`、`rank_take`），
  旧实现按纪律移入 `.trash/src_refactor_<时间戳>/`。
- `best_window.py` 与 `side_by_side.py` 从游戏技能里删掉：`skills/visual-taste/` 已有单一出处，
  文档改指向那里（`rank_take.py`、`side_by_side.py`）。
- 命名去缩写（`wf`→`workflow`、`nid`→`node_id`）；注释与 docstring 全中文；函数补类型注解；
  诊断走 `logging`，命令结果走 `print`。
- `tests/check_repo.py` 新增两项：列出 28 个必需 `src/` 模块；`src/` 每个模块必须含中文（纪律）。

### 生图口径（按本机实测能力重排）

H3 image（本地 `minimax_h3_image_pruned_w4a8`，`PH3ImageConditioning`，4K，首选）→ MOSS（`TextEncodeMOSSImageEdit` /
`MOSSImageControl` / `MOSSImageLayoutPrompt`，文字与排版）→ Z-Image turbo（抽卡）→ Qwen-Image-Edit（改图，
决定 3D 质量上限）→ Ignis gpt-image（云端积分，仅最后一公里，见 `FeiTuPrj_H3/Docs/IMGFLOW_04_Ignis.md`）。
注意 `MinimaxH3ImageNode` 是云端 partner 节点，不要与本地链路混用。

### 验证

- `check_repo`、`smoke_comfy`（1.5 s 拿到 PNG）、8 个审美量化单测、产线自检（0 项缺失）全绿。
- 重构后真跑一次抠图：2.0 s，`asset_log.json` 记录模型、prompt_id、文件。

## 0.0.1.2 — 技能归位与审美量化

### 结构

- 可安装技能统一放到 `skills/<技能名>/`：`skill/` → `skills/video-to-game-local/`，
  与新建的 `skills/visual-taste/` 同级，路径语义更清楚。
- `comfy_asset.py` 不再按"父目录第几层"找仓库根，改成按标记目录（`workflows/` + `tests/`）探测，
  技能目录再搬家也不会断（改坏了会直接报错，不静默降级）。
- 协作纪律改为**引用** <https://github.com/redcool/SimpleMcpServer>，不再在 `AGENTS.md` 里复制规则全文。

### 新增 skills/visual-taste（通用审美量化）

- `visual_metrics_core.py`：解码（ffmpeg → rgb24）、亮度/HSV、4 bit 分箱、分位数、熵、梯度、区域统计。
- `palette_report.py`：配色报告（主色、占比、艳度、对比、明暗分区、细节量），
  支持 `--profile quiet|vivid`、`--json`、`--strict`，以及 **`--baseline` 与参考比差值**。
- `frame_metrics.py`：单帧结构指标 + 层次检验（`--subject-box` 给出主体框，量化"主体跳不跳得出来"）。
- `side_by_side.py`、`rank_take_window.py`：改编自上游（MIT），行为一致、注释中文、变量名去缩写。
- 三个 reference：`metrics.md`（定义/公式/校准/误判）、`look-spec.md`（带数值的样子规格模板）、
  `compare-routine.md`（三个固定点、修改优先级、拒收标准）。
- 8 个 unittest 用例（ffmpeg 合成图，不依赖 ComfyUI），覆盖纯色、双色、层次、CLI JSON 合同、baseline 漂移。

### 抠图落地（原以为要装节点包，实际核心自带）

- ComfyUI 0.42 核心就有 `LoadBackgroundRemovalModel` + `RemoveBackground`，配 `background_removal/birefnet.safetensors`
  即可，**不需要第三方节点包**。已克隆的 ComfyUI-RMBG 按纪律移入 `.trash`（其依赖过重且会与嵌入式 Python 冲突）。
- 新增 `workflows/birefnet_cutout.json`：`LoadImage` → `RemoveBackground` → `JoinImageWithAlpha` → `SaveImage`。
  实测 512² 单张 **1.0 s**（首次含模型加载 120 s），输出 RGBA。
- 新增 `comfy_asset.py --upload TARGET=PATH`：把参考图复制成 `<内容哈希>_<原名>` 送进 ComfyUI `input/`，
  不覆盖同名文件、顺便破缓存；目录由 `COMFY_HOME` 或 `COMFY_INPUT` 指定。
- `comfy_health.py` 的抠图判定改用核心节点名（原来只认第三方节点包，会误报缺失）。
- 已知语义坑：`RemoveBackground` 输出的是**前景掩码**；无主体的画面（纯色示意图、风景）会被判成"背景为主"，
  抠出来是反的。用法说明见 `references/local-assets.md`。

### 校准（用真实素材，不是拍脑袋）

拿上游 gallery 的并排图切出参考半边与游戏半边各量一张，得到
`mean_saturation` 0.23–0.24、`contrast` 116–148、`palette_concentration_top5` 0.33–0.35、
`luma_entropy_bits` 3.7–4.1、`edge_density` 0.010–0.017。
第一版阈值（对比 ≤110、集中度 ≥0.45）把参考自己判成出界，于是按实测放宽；
并新增"与参考比差值"的模式——审美是"像不像参考"，不是"落不落在某个区间"。

### 修复

- 测试断言改用 ±2 容差：ffmpeg 生成 PNG 会走一次 RGB→YUV→RGB，通道值差 1。

### 已知缺口

- `src/` 模块化重构（编排器 + 全量中文注释 + 类型注解）未做，实现仍在 `skills/*/scripts/`。
- 本地抠图节点仍缺（`background_removal/birefnet.safetensors` 在位，ComfyUI 里只有云端节点）。
- 六个素材工作流未建（见 `workflows/README.md`）。

## 0.0.1.0 — M0 骨架

- 工程骨架、`.venv`（3.11.7 + pillow/trimesh，故意不装 torch）、ComfyUI 资产桥三件套
  （`comfy_client` / `comfy_asset` / `comfy_health`）、`tests/check_repo.py`、`tests/smoke_comfy.py`。
- 迁移上游脚本并修两处真实问题：`record_play.mjs` 的 Windows 浏览器探测、`study_video.py` 的旧帧残留。
- 实测：`comfy_health` 除抠图节点全绿；`smoke_comfy` 1.3 s 拿到 PNG；录屏器 231 帧 / 3.8 s / 60.5 fps。
# CHANGELOG

版本号规则 `x.y.z.w`：x（世代）、y（大版本）由人决定；z（大功能）、w（小改动）由 agent 维护。

**判定：z 只在该版本的功能清单全部完成（并有验证）时才升；未完结期间一律升 w。**
0.0.1 的功能清单（M0 骨架 → M1 工作流 → M2 动作链 → M3 首个游戏）尚未完结，
所以本次从 0.0.1.1 升到 **0.0.1.2**，不升 z。

## 0.0.1.10 — 三模型横向对比（当前）

同一提示词、同一场景，MOSS / H3 image / Ignis gpt-image 各出 2 版，量化对比：

| 模型 | 饱和 | 对比 | 高光 | 细节 | 结论 |
|---|---|---|---|---|---|
| MOSS | 0.199–0.209 | 68–107 | 0.002 | 0.017–0.025 | 色彩最足，画面平、没光源 |
| H3 image | 0.109–0.152 | 199–218 | 0.126–0.223 | 0.028–0.031 | 唯一会把残灯变成光源的，高光易过 |
| Ignis gpt-image | 0.053–0.060 | 108–115 | 0.002–0.005 | 0.034–0.035 | 细节最厚，偏灰暗 |

- 对比图 `games/pingchuan-rail/look/compare_models.jpg`（3×2）+ 单张预览 `look/compare/`（各 1280 宽）。
- **Ignis 首次接通并验证**：`USERPROFILE` 重定向 + `ignis.cmd imagine --model gpt-image --ar 16:9 --out`，
  实测单张 20–60 s、输出 2048×1152 约 4 MB。
- 分工写进 SPEC：锚点图用 H3，细节/精修用 Ignis，色彩与文字用 MOSS。
- 诚实说明：自造的"原生锐度"代理指标（512 裁切拉普拉斯均值）三家都在 118–125，**区分度不足**，已标注别当证据。

## 0.0.1.9 — 第一批素材 + 阈值按实测修正

- 三张锚点图（H3 image，12.3 / 6.1 / 7.1 s）：站台 2048²、隧道 2560×1440、竖井 1536×3072；
  入库预览在 `games/pingchuan-rail/look/`（原图在 `assets/`，不入库）。
- 三条音效（新增 `workflows/tangoflux_sfx.json`）：爬行 4 s / 残光嗡鸣 6 s / 弹射 2 s，均 44.1k 立体声。
- **阈值修正**：第一版审美阈值按"室外画廊"校准，把地下的正确锚点图判成出界
  （高光 0.05–0.20 vs 实测 0.003–0.090）。SPEC 改为实测基线 0.005–0.12，并把教训写进 visual-taste。
- **v2 三张被否决**：提示词写"局部绿色光池"，模型给的是整体偏绿（饱和 0.34）而光源更暗；
  结论记录为"颜色倾向靠提示词稳定，局部亮度靠后期"。
- 音效响度问题记录：TangoFlux 输出常 peak 0 dB 削顶，接游戏前需归一化。

## 0.0.1.8 — 可玩原型

- 按用户确认的结局改定：**蠕虫钻地 → 千辛万苦 → 找到冷冻舱**（不再有二选一）。
- 新增 `games/pingchuan-rail/game/index.html`：侧视 3D 可玩原型（纯程序化几何，零素材、零 GPU）。
  贴壁爬行 / 蓄力弹射 / 金属保速与粉尘归零 / 扫描锥 / 检查点 / 抵达冷冻舱结局，全部实现。
- 新增 `tests/smoke_game.mjs`：起静态服务 + 系统 Chrome，按键驱动并断言 9 个路口、结局、帧率、控制台错误。
  首次跑就抓到 3 个真问题（离开表面被立刻吸回、共线接续缺失、竖井横档不在端点），已修。
- 作废提交 `777649c`（v0.0.2.0）：git 提交不能移动，只能改写或记录；本项目选择**记录**，
  说明落在本地 `.trash/obsolete_commit_777649c.md`，不改写已推送历史。

## 0.0.1.7 — 首个游戏立项：骸轨（平川地铁）

- 概念定档：一局 3–5 分钟的"另类跑酷 + 探索"，主角是**环节蠕虫**（不需要骨骼绑定），
  机制只有三件事：贴壁爬、蓄力弹射、微光。世界取自小说《废土中的正义》第 25/35/37 章。
- 新增 `games/pingchuan-rail/`：`SPEC.md`（原文依据表 + 配色 + 关卡节拍 + 验收）、`README.md`、
  `video-prompts.md`（5 条 H3 参考视频提示词，各验一个设计问题）。
- 未做任何生成：GPU 仍在渲染 MV。

## 0.0.1.6 — MOSS 两个工作流入库

按 `FeiTuPrj_H3/Docs/moss生图流程.md` 与那边跑通的 `WorkFlows/MossImage/moss_common.py` 复刻：

- `workflows/moss_t2i.json`：`UNETLoader(moss_image_sft_int8_convrot)` + `CLIPLoader(type=moss_image, qwen3.5_9b_w4a8_gptq)`
  + `VAELoader(flux2-vae_small)` → `CLIPTextEncode` 正/负 → **`EmptyFlux2LatentImage`** →
  `KSampler(50 步, CFG 3.0, euler, normal)` → `VAEDecode` → `SaveImage`。
- `workflows/moss_edit.json`：edit LoRA（1.0）+ `SkipLayerGuidanceDiTSimple(single_layers="22")`、
  `TextEncodeMOSSImageEdit(edit_format=Moss-Image-Edit)` ×2、`KSampler(30 步, CFG 4.0)`；
  参考图经 `ImageScaleToTotalPixels`(1.0MP/16px) 进 **扁平键 `images.image_0`**。
- 文档补 MOSS 实测口径（10–14 s、16 倍数、负面词、修图 Keep 模板、autogrow 坑）。
- **未跑**：GPU 正在渲染 MV，等工作流齐全且卡空出来再实测。
- 版本按纪律只升 w：0.0.1 的 M1.5 功能清单未完结。

## 0.0.1.5 — H3 image 跑通

### 修复：用错了模板

上一版按 `image_p_h3_t2i`（p-h3-image = fl2va + LoRA）搭图，与机器上的 image 权重不通用。
正确模板是 `image_minimax_h3_image_t2i`：`MiniMaxH3ImageConditioning`（**不是** `PH3ImageConditioning`）
→ `KSampler`（**不是** `SamplerCustomAdvanced`）。

### 配方（用户确认 + 本机实测）

| 节点 | 模板默认 | 本机 |
|---|---|---|
| UNETLoader | `minimax_h3_image_pruned_int8_convrot` | `minimax_h3_image_pruned_w4a8` |
| CLIPLoader（主） | `qwen3vl_32b_minimax_h3_int8_convrot` | `qwen3vl_32b_minimax_h3_nvfp4_awq` |
| VAELoader | `minimax_h3_image_vae_fp16` | 不变 |
| CLIPLoader（扩写） | `qwen3.5_9b_w4a8_gptq` | 不变，默认关闭 |

采样参数：**euler + simple、6 步、CFG 1、denoise 1**（不动）。分辨率默认 3104×3104。

### 实测

- 冷启 2048²：242.4 s（装 11.7 GB UNet + 32B 文本编码器）
- 换 seed 再来一张：346.1 s（仍在装卸模型）
- **模型常驻后 3104×3104：11.2 s**（9.6 MP，14 MB PNG）
- 结论写进 `references/local-assets.md`：成本在装卸不在采样，连续出图才划算。

## 0.0.1.4 — H3 生图探路 + 失败可读化

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
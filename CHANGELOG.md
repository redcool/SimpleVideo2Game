# CHANGELOG

版本号规则 `x.y.z.w`：x（世代）、y（大版本）由人决定；z（大功能）、w（小改动）由 agent 维护。

**判定：z 只在该版本的功能清单全部完成（并有验证）时才升；未完结期间一律升 w。**
0.0.1 的功能清单（M0 骨架 → M1 工作流 → M2 动作链 → M3 首个游戏）尚未完结，
所以本次从 0.0.1.1 升到 **0.0.1.2**，不升 z。

## 0.0.1.2 — 技能归位与审美量化（当前）

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
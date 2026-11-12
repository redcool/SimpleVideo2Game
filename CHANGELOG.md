# CHANGELOG

## 0.1.0 — M0 骨架（当前）

- 新建工程：上游 `lovisdotio/video-to-game` 的克隆移到 `_ref/`（只读参考），方法论迁移进 `skill/`。
- `.venv`：Python 3.11.7 + `pillow`/`trimesh`；**故意不装 torch**（本机 5090 需要 cu130，GPU 计算只走 ComfyUI）。
- 新增 ComfyUI 资产桥：
  - `skill/scripts/comfy_client.py`：`/prompt` → `/history` → `/view`，模型/节点/队列查询，工作流改写工具。
  - `skill/scripts/comfy_asset.py`：上游 `fal_asset.py` 的本地版（`--set` / `--seed` / `--dry-run` / `--list`），
    每次生成追加 `assets/asset_log.json`（工作流、模型、seed、耗时、文件）。
  - `skill/scripts/comfy_health.py`：一条命令回答"这台机器还缺什么"——主机工具链、ComfyUI 版本/GPU、
    1173 个节点类按能力分组、关键模型文件是否在位。
- 迁移上游脚本并修两个真实问题：
  - `record_play.mjs`：补 Windows / `CHROME_PATH` 的浏览器探测（原来只认 macOS/Linux 三条路径，Windows 上必挂），
    并打印实际用的是哪个浏览器。
  - `study_video.py`：复跑时清掉旧的 `f_*.jpg`，帧表不再错位。
- 文档：`README`、`AGENTS`、`NOTICE`（上游 MIT 归属）、`skill/references/local-assets.md`
  （fal 端点 → 本机模型/节点的对照表，含 Hunyuan3D / Trellis2 / H3 / TangoFlux / ACE-Step 的真实节点签名）。
- 测试：`tests/check_repo.py`（结构/断链/语法/工作流格式/绝对路径/密钥/体积）、`tests/smoke_comfy.py`（资产桥端到端）。
- 实测：`comfy_health` 全绿（除抠图节点）；`smoke_comfy` 1.3 s 拿到 PNG；
  录屏器在 Windows + 系统 Chrome 上 231 帧 / 3.8 s / 60.5 fps 出片。

### 已知缺口

- **本地抠图节点缺失**：`background_removal/birefnet.safetensors` 在位，但 ComfyUI 里只有 Bria/Recraft/Tripo
  这些云端节点。要么装本地 BiRefNet/RMBG 节点包，要么在 venv 里用 rembg 兜底。
- 七个素材工作流还没建（见 `workflows/README.md` 的待建表）。
- 绑定（Mixamo）与 UniMate 动作链还没接进本工程。

### 下一步（M1）

1. `workflows/zimage_t2i.json`（最快看到图）→ 2. `birefnet_cutout` → 3. `hunyuan3d_i23d`
→ 4. `tangoflux_sfx` → 5. `minimax_music3` → 6. `h3_video`。每建成一个，把 `asset_log.json` 的耗时抄回
`local-assets.md` 的成本表。

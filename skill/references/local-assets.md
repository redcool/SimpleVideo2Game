# 本机素材产线（替代上游的 fal-assets.md）

规则：游戏里的每一张图、每一个 3D 模型、每一条音效和音乐，都由**本机 ComfyUI** 生成，
用视频自己的帧当参考图，这样素材和视频是同一个世界。手画的、下载的、云端偷偷调的，都不算。

跑一个任务：

```powershell
python skill\scripts\comfy_asset.py <workflow> -o games\<g>\assets --name <名字> \
    --set prompt="..." --set 12.image=ref.png --seed 7
```

它做四件事：上传不了文件（所以参考图要先放进 ComfyUI 的 `input/`）、提交、轮询、下载，
并追加 `assets/asset_log.json`。**一次一个任务**：看完结果再要下一个。GPU 是串行的，
同时排五个任务只会让你等更久，还看不清哪个好。

## 上游 fal 端点 → 本机等价物

| 上游（fal） | 本机实现 | 状态 |
|---|---|---|
| `fal-ai/nano-banana-pro(+edit)` 概念图/贴图/天空 | **Qwen-Image-Edit 2511**（`qwen_image_edit_2511_fp8mixed`）、**Z-Image turbo**、Krea2 turbo、Ideogram4 | 模型在位，工作流待建 |
| `fal-ai/birefnet/v2` 抠图 | BiRefNet（`background_removal/birefnet.safetensors`） | **模型在位，本地节点缺失**（见下） |
| `meshy/v7.1/image-to-3d`、tripo、hunyuan3d | **Hunyuan3D v2.1**（核心节点）或 **Trellis2**（核心节点） | 模型 + 节点在位，工作流待建 |
| `fal-ai/meshy/rigging/multi-animation` 骨骼动画 | **Mixamo 免费自动绑定** + 本机 **UniMate**（文本→动作）/ **GVHMR**（视频动补） | 独立工程，见文末 |
| `fal-ai/elevenlabs/sound-effects/v2` 音效 | **TangoFlux**（`TangoFluxSampler` → `TangoFluxVAEDecodeAndPlay`）；备选 Stable Audio Open | 模型在位，工作流待建 |
| `elevenlabs/music/v2.5` 音乐 | **MiniMax Music 3**（`MiniMaxMusic3TextEncode`）、**ACE-Step 1.5**（`TextEncodeAceStepAudio1.5`）、YuE2（带唱） | 模型在位，工作流待建 |
| `minimax/h3-max/text-to-video` gameplay 视频 | **MiniMax H3 本地**：`MiniMaxH3EasyLoader` + `MiniMaxH3Easy`，或一把梭 `H3OneNode` | 权重 + 节点在位，工作流待建 |

## 逐条链路（节点名是在本机 ComfyUI 0.42 上核对过的）

### 1. 概念图 / 贴图 / 视差层（图像）

- **Z-Image turbo**：`LoadZImageModel //ZImagePowerNodes`（checkpoint）→ `CLIPTextEncode` ×2 →
  `KSampler`（steps 少、cfg 低，turbo 就是快）→ `VAEDecode` → `SaveImage`。
  适合批量出概念图和"大概长这样"的探索。**先低分辨率抽卡，选中的再放大**。
- **Qwen-Image-Edit 2511**：`diffusion_models/qwen_image_edit_2511_fp8mixed`。
  它的用途是**改图**：给一张视频帧 + "the same character alone, full body, A-pose, plain light grey
  background, same art style"，得到能喂 3D 的角色图。这是最有价值的一步，因为 3D 的质量上限就是这张图。
- 贴图要点：`seamless tileable texture, top-down, flat even light, no shadows, no perspective`，
  拿到先 3×3 平铺看一眼再接缝。
- 视差层：一张很宽的天空/远山，要求 `isolated on a flat white background`，抠出来贴平面，按远近分层。

### 2. 抠图（**当前缺口**）

本机 `models/background_removal` 里有 BiRefNet 权重，但 **ComfyUI 里没有本地抠图节点**
（`object_info` 里只有 Bria / Recraft / Tripo 这些云端节点）。二选一：

1. **装一个本地节点包**（推荐，保持第 3 步统一走 ComfyUI）：ComfyUI-RMBG 一类支持 BiRefNet/RMBG 的打包，
   装完 `python skill\scripts\comfy_health.py` 会从 ❌ 变 ✅。
2. **venv 里做**（`pip install rembg onnxruntime`，CPU 也行）：写个小脚本抠完直接落到 `assets/`，
   但要在 `asset_log.json` 里手记一笔，别破坏"每个素材都有出处"的规矩。

抠图质量决定 3D 质量：边缘要干净、不要留灰边、透明区不要有半透明噪点。抠完看一眼 alpha 通道。

### 3. 图生 3D（Hunyuan3D v2.1）

节点链（本机核对）：

```text
LoadImage ─────────────► CLIPVisionEncode ◄── CLIPVisionLoader (dinov2)
                              │
EmptyLatentHunyuan3Dv2 ──┐    ▼
   (resolution, batch)   │  Hunyuan3Dv2Conditioning ──► positive / negative
                         ▼            │
CheckpointLoaderSimple (hunyuan_3d_v2.1) ──► MODEL ──► KSampler ──► VAEDecodeHunyuan3D (VOXEL)
                                                          │
                                     VoxelToMesh / VoxelToMeshBasic (MESH) ──► SaveGLB
```

- 多视角更稳：`Hunyuan3Dv2ConditioningMultiView` 接受 `front / left / back / right`，
  四张图用 Qwen-Image-Edit 从同一张概念图转出来。
- 贴图：`BakeTextureFromVoxel`、`PaintMesh`、`ApplyTextureToMesh`、`BakeNormalMapFromMesh`，
  还有 `DecimateMesh`（面数）、`RemeshMesh`（拓扑）、`UnwrapMesh`（UV）、`MeshSmoothNormals`、`FillHoles`。
  **游戏用：先 Decimate 到 5k–20k 面，再 ShowNormals**。
- 导出：`SaveGLB`（`mesh` + `filename_prefix`）写进 ComfyUI 的 `output/`，`comfy_asset.py` 负责搬回来。
- **Trellis2 备选**：`EmptyTrellis2LatentStructure` → `Trellis2Conditioning` → 采样 →
  `VaeDecodeStructureTrellis2`（VOXEL）→ `Trellis2ShapeStage` / `Trellis2TextureStage` →
  `VaeDecodeShapeTrellis`（MESH）/ `VaeDecodeTextureTrellis`（VOXEL）。Trellis2 出带 PBR 的成品更省事。

### 4. 音效与音乐

- **音效（首选 TangoFlux，最省事）**：`TangoFluxLoader` → `TangoFluxSampler`
  （`prompt`, `steps`, `guidance_scale`, `duration`, `seed`）→ `TangoFluxVAEDecodeAndPlay`
  （直接存盘，`filename_prefix`/`format`）。一条音效一个 seed。
- **SFX 备选 Stable Audio Open**：`CheckpointLoaderSimple(stable-audio-open-1.0)` → `CLIPTextEncode` 正/负 →
  `ConditioningStableAudio(seconds_start, seconds_total)` → `KSampler` + `EmptyLatentAudio` →
  `VAEDecodeAudio` → `SaveAudio`。
- **音乐（首选 MiniMax Music 3）**：`MiniMaxMusic3TextEncode(clip, caption, lyrics, seed, max_duration)`
  + `EmptyMiniMaxMusic3LatentAudio(seconds)` → `KSampler` → `VAEDecodeAudio` → `SaveAudio`。
- **音乐（ACE-Step 1.5）**：`TextEncodeAceStepAudio1.5(clip, tags, lyrics, seed, bpm, duration, ...)` +
  `EmptyAceStep1.5LatentAudio(seconds)` → `KSampler` → `VAEDecodeAudio` → `SaveAudio`。
- 处理：`AudioAdjustVolume`、`AudioEqualizer3Band`、`AudioMerge`、`TrimAudioDuration` 够做混音；
  **音效要比音乐响**，音乐压到 -18 LUFS 一带，不然玩家只听见音乐。
- 循环音效（风、引擎、雨）要标 loop，并检查首尾接缝。

### 5. gameplay 视频（MiniMax H3，本地）

- **一把梭**：`H3OneNode`（输出 poster + video），提示词直接给。适合第一次试。
- **可控**：`MiniMaxH3EasyLoader(fl2va_model, ref2va_model, text_encoder, video_vae, audio_vae)` →
  `MiniMaxH3Easy(h3_bundle, mode, prompt, resolution, aspect_ratio, width, height, seconds, fps, ...)`，
  另有 `MiniMaxH3ReferenceToVideo`、`MiniMaxH3ImageToVideo`、`MiniMaxH3Director`（多参考/延续）。
- 视频提示词的套路就是上游 `prompts/gameplay-video-prompts.md`：一句话概念 + 一个动词 + 可玩机位 + 无 HUD
  + 一句美术方向 + 10–15 s。本机免费，所以**生成 5–10 条选一条**，这是本地化最大的红利，别浪费。
- 注意：H3 权重是 int8 且很大（约 19.5 GB ×2），跑之前先让 ComfyUI 卸载别的模型，
  不然 34 GB 显存会被切开抢。

## 绑定与动作（不在这台 ComfyUI 里做）

UniMate **要求模型已经绑定**（armature + 蒙皮网格），它不做自动绑骨。所以：

1. **绑定**：Mixamo（免费，上传 FBX/OBJ → 自动骨架；从 GLB 转 FBX 用 Blender）——
   一个角色绑一次，所有动作复用。或者 Tripo Auto Rig（付费）。**Blender 5.2 在本机 PATH 上**。
2. **动作**（两条路，按视频风格选）：
   - **文本→动作**（本机 UniMate）：适合风格化角色、夸张动作；产物是 60 帧原地片段，
     要循环化（走/跑用 `make_loop.py`，待机用 `loop_close.py`），根位移拉平交给引擎。
   - **视频动补**（GVHMR，`Motion2MixamoRig`）：适合**写实**视频、真实机位。给焦距是必要动作
     （手机主摄 26 mm @1920 ≈ 1387 px），不给会高估深度约 65%。
     产出 `mixamo_character_grounded.glb/.fbx` + 质检报告（穿模 < 15%、脚锁 < 30 cm 才 PASS）。
3. **导出**：GLB（Three.js 直接吃）或 FBX（Unity）。

## 搬进 Three.js 之前的硬性归一化

每个 GLB 进来都要：**缩放到已知身高**、**脚底在 y=0**、**朝 -Z**、**删掉不需要的动画轨道**。
不归一化就会出现"这个角色比房子还高"和"一半身子在土里"，而且每次都是同一个坑。

- 贴图：道具 1K、地形 2K，统一 WebP；贴图 > 2K 在浏览器里吃带宽不还你画质。
- 面数：角色 5k–20k，道具 < 3k，重复的东西 InstancedMesh。
- 体积：一个游戏 `assets/` 控制在 30 MB 以内（本地生成很容易失控），
  用 `npx @gltf-transform/cli optimize` 压一遍再进 `game/`。

## 成本与耗时

钱是 0，时间是主要成本。第一次跑完把 `asset_log.json` 里的 `seconds` 抄回这张表：

| 任务 | 显存占用（估） | 实测耗时 | 备注 |
|---|---|---|---|
| Z-Image turbo 1024² | ~12 GB | 待测 | 抽卡主力 |
| Qwen-Image-Edit 1024²(fp8) | ~20 GB | 待测 | 改图，最影响 3D 质量 |
| Hunyuan3D v2.1 一个模型 | ~10 GB | 待测 | 加上贴图/减面另算 |
| TangoFlux 一条音效 | ~6 GB | 待测 | 快 |
| ACE-Step / Music3 一段音乐 | ~10 GB | 待测 | 分钟级 |
| H3 一条 10–15 s 1080p | ~20 GB+ | 待测 | 最贵，先小分辨率试 |

## 常见失败

- **出来的东西太小/太大**：不是模型坏了，是没归一化。先量 bbox。
- **3D 是个扁片**：概念图侧视/侧脸，或抠图留了背景。换正视角、重抠。
- **手/脚糊成一团**：image-to-3D 的通病。游戏中远景 + 剪影可救；近景主角要么换多视角，要么接受并设计成剪影角色。
- **素材和视频不是一个世界**：参考图给少了。每次生成都塞一张视频帧进 `image_urls`/`LoadImage`。
- **等待时间爆炸**：一次排五个任务、或者忘了卸载上一个模型。串行 + `/free`。

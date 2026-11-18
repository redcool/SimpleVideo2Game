# 本机素材产线（替代上游的 fal-assets.md）

写提示词之前先读 `prompting-manual.md`（光要写成物理量、材质要写成物理属性、H3 没有负分支）。

规则：游戏里的每一张图、每一个 3D 模型、每一条音效和音乐，都由**本机 ComfyUI** 生成，
用视频自己的帧当参考图，这样素材和视频是同一个世界。手画的、下载的、云端偷偷调的，都不算。

跑一个任务：

```powershell
python skills\video-to-game-local\scripts\comfy_asset.py <workflow> -o games\<g>\assets --name <名字> \
    --set prompt="..." --set 12.image=ref.png --seed 7
```

它做四件事：上传不了文件（所以参考图要先放进 ComfyUI 的 `input/`）、提交、轮询、下载，
并追加 `assets/asset_log.json`。**一次一个任务**：看完结果再要下一个。GPU 是串行的，
同时排五个任务只会让你等更久，还看不清哪个好。

## 上游 fal 端点 → 本机等价物

| 上游（fal） | 本机实现 | 状态 |
|---|---|---|
| `fal-ai/nano-banana-pro(+edit)` 概念图/贴图/天空 | **H3 image（本地，4K，首选，✅ 已跑通）** → **MOSS（本地，排版/局部精修）** → Z-Image turbo（抽卡）→ Qwen-Image-Edit（改图）；云端兜底 Ignis gpt-image2 | H3 image 可用；MOSS/Ignis 待接线 |
| `fal-ai/birefnet/v2` 抠图 | **ComfyUI 核心内置**：`LoadBackgroundRemovalModel` + `RemoveBackground`（`background_removal/birefnet.safetensors`） | ✅ `workflows/birefnet_cutout.json` 已可用 |
| `meshy/v7.1/image-to-3d`、tripo、hunyuan3d | **Hunyuan3D v2.1**（核心节点）或 **Trellis2**（核心节点） | 模型 + 节点在位，工作流待建 |
| `fal-ai/meshy/rigging/multi-animation` 骨骼动画 | **Mixamo 免费自动绑定** + 本机 **UniMate**（文本→动作）/ **GVHMR**（视频动补） | 独立工程，见文末 |
| `fal-ai/elevenlabs/sound-effects/v2` 音效 | **TangoFlux**（`TangoFluxSampler` → `TangoFluxVAEDecodeAndPlay`）；备选 Stable Audio Open | 模型在位，工作流待建 |
| `elevenlabs/music/v2.5` 音乐 | **MiniMax Music 3**（`MiniMaxMusic3TextEncode`）、**ACE-Step 1.5**（`TextEncodeAceStepAudio1.5`）、YuE2（带唱） | 模型在位，工作流待建 |
| `minimax/h3-max/text-to-video` gameplay 视频 | **MiniMax H3 本地**：`MiniMaxH3EasyLoader` + `MiniMaxH3Easy`，或一把梭 `H3OneNode` | 权重 + 节点在位，工作流待建 |

## 逐条链路（节点名是在本机 ComfyUI 0.42 上核对过的）

### 1. 概念图 / 贴图 / 视差层（图像）

### 三模型画像（2026-11-16 实测，同一提示词、同一场景各出 2 版）

| 模型 | 尺寸 | 饱和 | 对比 | 高光 | 细节 | 熵 | 结论 |
|---|---|---|---|---|---|---|---|
| MOSS sft | 1536×864 | **0.199–0.209** | 68–107 | 0.002 | 0.017–0.025 | 3.4–4.0 | 色彩最足，但**画面平、没有光源** |
| H3 image | 2048×1152 | 0.109–0.152 | **199–218** | **0.126–0.223** | 0.028–0.031 | **4.6–4.7** | 光影最强、最"电影"，代价是高光容易过 |
| Ignis gpt-image | 2048×1152 | 0.053–0.060 | 108–115 | 0.002–0.005 | **0.034–0.035** | 4.10 | **细节最厚**，但整体偏灰偏暗 |

用法建议（写进 SPEC 的分工）：
- **锚点图 / 光影关系** → H3 image（它最会把"几盏残灯"变成真正的光源）；
- **精修 / 需要结构细节**（机械、残骸、铭牌）→ Ignis gpt-image（细节密度最高，且有积分就用）；
- **要色彩或中文排版** → MOSS（饱和最足、文字最准，但别指望它给光影）。

⚠️ 一个测量诚实说明：我又算了个"原生锐度"（512 中心裁切的拉普拉斯均值），三家都在 118–125，
**区分度不足**——这个代理指标在这个尺度上失效了，别拿它当"谁更清晰"的证据。要看清晰度就放大看局部。

### Ignis gpt-image 已验证可用的调用方式（本机实测）

```powershell
$env:USERPROFILE = "<FeiTuPrj_H3>/.tools/fake-home"     # 里面要有 .ignis/config.json
& "<FeiTuPrj_H3>/.tools/ignis/node_modules/.bin/ignis.cmd" whoami
& "...\ignis.cmd" imagine "一句连贯的描述" --model gpt-image --ar 16:9 --out <输出目录>
```
输出是 `<随机名>.png`（实测 2048×1152、约 4 MB），命令自己下载到 `--out`。
实测单张 20–60 s；走个人积分。**注意它不吃"局部光池"这类提示词**，要亮点靠后期。

按"准不准"排序，别一上来就用旧的 turbo 模型：

1. **H3 image（首选，本机，支持 4K）—— 已跑通（2026-11-16 实测）**

   正确模板是 ComfyUI 自带的 `image_minimax_h3_image_t2i.json`（**不是** `image_p_h3_t2i.json`，
   后者是 p-h3-image 的 fl2va+LoRA 路线，与本机权重不通用）。配方：

   ```text
   UNETLoader(minimax_h3_image_pruned_w4a8)        → MODEL
   CLIPLoader(qwen3vl_32b_minimax_h3_nvfp4_awq, type=minimax) → CLIP
   VAELoader(minimax_h3_image_vae_fp16)            → VAE
   MiniMaxH3ImageConditioning(clip, vae, prompt, width, height) → positive + latent
   ConditioningZeroOut(positive)                   → negative
   KSampler(steps=6, cfg=1.0, euler, simple, denoise=1.0) → VAEDecode → SaveImage
   ```

   - **采样参数别动**：euler + simple、6 步、CFG 1、denoise 1。这是蒸馏好的固定配方。
   - 本机权重映射：模板默认 `minimax_h3_image_pruned_int8_convrot` / `qwen3vl_32b_minimax_h3_int8_convrot`，
     本机用 **`..._pruned_w4a8`** 与 **`..._nvfp4_awq`**，VAE 与扩写器不用改。
   - 分辨率：模板默认 3104×3104（4MP 起，官方说明低分辨率效果差）。
   - **扩写器（可选）**：模板里还有第二个 `CLIPLoader(qwen3.5_9b_w4a8_gptq)` + `TextGenerateV2`，
     负责把一句话扩写成详细描述并挑画幅，默认**关闭**（`ComfySwitchNode=false`）。想要长描述再打开。

   实测（RTX 5090 / 31.8 GB）：

   | 场景 | 耗时 |
   |---|---|
   | 冷启（装 11.7 GB UNet + 32B 文本编码器） | 242 s |
   | 换 seed 再来一张（仍在装卸模型） | 346 s |
   | **模型常驻后的 3104×3104** | **11.2 s** |

   结论：成本几乎全在**模型装卸**，不在采样。所以连续出多张要比一张一张来划算得多；
   跑之前先 `/free` 卸掉别的模型，跑的过程中别切图放大降分辨率。

   两个坑（都踩过，别再踩）：`PH3ImageConditioning` + `SamplerCustomAdvanced` 那条路对应 p-h3-image
   （fl2va + LoRA），用本机 image 权重会报 `IndexError: tuple index out of range`；
   `MinimaxH3ImageNode`（partner/image/MiniMax）是**云端 API 版**，别与本机链路混用。
2. **MOSS（本机主力打样，文字/排版/指令修图最强）** —— 配方已核实（来源：`FeiTuPrj_H3/Docs/moss生图流程.md`，
   那边有跑通的 `moss_common.py`，本仓库的 `workflows/moss_t2i.json`、`moss_edit.json` 就是照它复刻的）

   - 三个必需模型：`moss_image_sft_int8_convrot`（diffusion_models）、
     `qwen3.5_9b_w4a8_gptq`（text_encoders，`type=moss_image`）、`flux2-vae_small`（vae）；
     修图再加 `moss_image_edit_lora_rank_64_bf16`。
   - **文生图参数**：`KSampler` 50 步 / CFG 3.0 / `euler` / `normal` / denoise 1.0，
     latent 用 **`EmptyFlux2LatentImage`**（不是 `EmptyLatentImage`）。
     负面词固定：`nsfw, worst quality, bad anatomy, watermark, jpeg artifact`。
     宽高必须是 **16 的倍数**，总像素 1M–2M（本次默认 1536×864）。
   - **指令修图参数**：挂 edit LoRA（强度 1.0）+ `SkipLayerGuidanceDiTSimple`（`single_layers="22"`，
     0→1.0 全段），30 步 / CFG 4.0，两个 `TextEncodeMOSSImageEdit` 的 `edit_format` 必须都是
     `Moss-Image-Edit`。指令模板：`Change only the <X> to <Y>. Keep the character, face, hair, pose,
     background and composition unchanged.`
   - **API 坑**：修图节点的图输入是 autogrow，必须写扁平键 `"images.image_0"`；写成嵌套 dict 会报
     `required_input_missing images.image_0`。本仓库用 `--upload 39.images.image_0=ref.png` 正好命中。
   - 实测（对方机器，同款 5090）：1024² / 30 步 **10.3 s**；1536×864 / 50 步 **14.0 s**；
     修图 1MP / 30 步 **12.0 s**。中文标题排版逐字正确（1024×1536 海报 10.0 s）。
3. **Z-Image turbo（抽卡）**：`LoadZImageModel //ZImagePowerNodes` + `KSampler`（步数少、cfg 低）→ 快速出十张定方向，
   **选中的再用 H3 image 或者 Qwen-Edit 精修**，不要用 turbo 出成品。
4. **Qwen-Image-Edit 2511（改图/换风格）**：`diffusion_models/qwen_image_edit_2511_fp8mixed`。
   给视频帧 + "the same character alone, full body, A-pose, plain light grey background, same art style"，
   得到能喂 3D 的角色图 —— **3D 的质量上限就是这张图**。
5. **Ignis gpt-image（云端，积分，最后一公里）**：本机不能/不便精修的高清定妆图才走它（2560×1440 实测）。
   CLI 在另一个工程（`<FeiTuPrj_H3>/.tools/ignis/node_modules/.bin/ignis.cmd`），用法见
   `H:\Works\FeiTuPrj_H3\Docs\IMGFLOW_04_Ignis.md`：`ignis imagine "..." --model gpt-image --ar 16:9 --out ./outputs`。
   Windows 上要先 `$env:USERPROFILE` 重定向到带 `.ignis\config.json` 的目录。**它走积分，不当默认路径。**
- 贴图要点：`seamless tileable texture, top-down, flat even light, no shadows, no perspective`，
  拿到先 3×3 平铺看一眼再接缝。
- 视差层：一张很宽的天空/远山，要求 `isolated on a flat white background`，抠出来贴平面，按远近分层。

### 2. 抠图（**当前缺口**）

本机 `models/background_removal` 里有 BiRefNet 权重，但 **ComfyUI 里没有本地抠图节点**
（`object_info` 里只有 Bria / Recraft / Tripo 这些云端节点）。二选一：

1. **装一个本地节点包**（推荐，保持第 3 步统一走 ComfyUI）：ComfyUI-RMBG 一类支持 BiRefNet/RMBG 的打包，
   装完 `python skills\video-to-game-local\scripts\comfy_health.py` 会从 ❌ 变 ✅。
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
  （`prompt`, `steps`=50, `guidance_scale`=3, `duration`=秒, `seed`）→ `TangoFluxVAEDecodeAndPlay`
  （直接存盘，`filename_prefix`/`format`=`wav`）。工作流 `workflows/tangoflux_sfx.json`。
  实测（2026-11-16）：4 s 音效 **11.1 s**、6 s **3.0 s**、2 s **3.1 s**（模型常驻后很快）。
  **注意响度**：出来的 wav 常是 peak 0 dB（削顶）、mean −26 到 −34 dB，接进游戏前统一归一化
  （音效 −16 LUFS 左右，音乐压到 −18）。
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

- **已验证的配方（本仓库 `workflows/h3_video.json`，照官方 `video_minimax_h3_t2v` 模板）**：
  `UNETLoader(minimax_h3_fl2va_pruned_int8_convrot)` + `CLIPLoader(qwen3vl_32b_minimax_h3_nvfp4_awq, minimax)`
  + 两个 `VAELoader`（`minimax_h3_video_vae_fp16` / `minimax_h3_audio_vae_fp32`）
  → `MiniMaxH3ImageToVideo(clip, vae, prompt, width, height, length)` → `BasicGuider`
  → `KSamplerSelect(res_multistep)` + `BasicScheduler(simple, 20 步)` + `RandomNoise`
  → `SamplerCustomAdvanced` → `VAEDecode`(视频) + `VAEDecodeAudio`(音轨) → `CreateVideo(fps=24, audio)` → `SaveVideo`。
  **注意**：`length` 要满足 `(length - 5) % 17 == 0`（5/22/39/56/73/90/107/124…），124 帧 ≈ 5.2 s。
  官方模板里那个 `fl2v_turbo_8step` LoRA 本机没有，所以走 **20 步**基础档。
- **实测（RTX 5090）**：1152×640、124 帧、20 步 —— **150–190 s / 条**；产出 H.264 + **AAC 音轨**（H3 自带声音）。
- **踩过的坑：H3 视频会「欠曝」**。同一批 5 条里，一条整片发灰（粉尘糊满）、两条几乎全黑（饱和 0.55/0.38）。
  提示词加 `well exposed, readable midtones, clearly visible subject, fog only in the far background`
  能救回一部分（弹射片饱和 0.101 → 0.274、熵 3.80 → 4.25），但**极暗场景仍需要后期提亮**。
  另外 20 步 0.7 MP 的细节偏薄（edge 0.008–0.027，对比 H3 image 的 0.028–0.031）。
- **一把梭**：`H3OneNode`（输出 poster + video），但它的输入几乎全靠界面动态控件，API 里只有一个 `prompt`，不适合脚本化。
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
| BiRefNet 抠图 512² | ~4 GB | **1.0 s**（首次含加载 120 s） | 单个 `RemoveBackground` 节点 |
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
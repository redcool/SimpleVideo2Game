# workflows/

ComfyUI 的**API 格式**工作流，一个文件 = 流水线里的一个素材任务。`comfy_asset.py` 直接吃这里的文件。

## 格式（必须是 API 格式）

在 ComfyUI 里调好一条链路 → 菜单 **Workflow → Export (API)** → 存成 JSON → 放这里。
文件形如 `{"节点id": {"class_type": "...", "inputs": {...}}}`。

GUI 格式（带 `nodes` / `links` 数组的那种）会被 `comfy_asset.py` 明确拒绝，因为它的节点 id 和连线方式都不同。
把 GUI 工作流当成"给人看的图纸"提交进仓库是常见错误，别犯。

## 约定

1. **文件名 = 任务名**，全小写下划线，例如 `zimage_t2i.json`、`birefnet_cutout.json`、`hunyuan3d_i23d.json`。
2. **必须可配 seed**：图里要有 `seed` 或 `noise_seed` 输入，`--seed` 才能复现。
3. **可注入的字段**要挑得出来：`--set prompt="..."`、`--set 7.image=xxx.png`。
   想注入的值最好落在唯一节点上，多个节点同名输入会被一起改（脚本会打印改了几个）。
4. **输出节点**用 `SaveImage` / `SaveAudio` / `SaveGLB`，别只用 Preview：preview 存的是临时文件。
5. **不要写死本机路径**：`LoadImage` 只写文件名，文件放 ComfyUI 的 `input/` 目录，
   或者用 `--set` 从命令行给。提交前 `python tests/check_repo.py` 会查绝对路径。

## 现有

| 文件 | 用途 | 需要模型 |
|---|---|---|
| `smoke_empty_image.json` | 资产桥自检：纯 CPU、1 秒出图，验证 提交→轮询→下载→记账 整条路 | 无 |

## 待建（M1，按这个顺序做，每建成一个就在这里划掉）

| 任务 | 主要节点（本机已装） | 备注 |
|---|---|---|
| `zimage_t2i` 文生图 / 概念图 | `LoadZImageModel //ZImagePowerNodes`（或 `CheckpointLoaderSimple`）+ `CLIPTextEncode` + `KSampler` + `VAEDecode` + `SaveImage` | Z-Image turbo 步数少，适合批量出概念图 |
| `qwen_edit` 图生图（改图/换风格） | Qwen-Image-Edit 2511 权重（`diffusion_models`） | 用视频帧当参考图改出可用素材 |
| `birefnet_cutout` 抠图 | BiRefNet / RMBG（`background_removal`） | 出干净 alpha，喂 3D |
| `hunyuan3d_i23d` 图生 3D | `EmptyLatentHunyuan3Dv2` + `Hunyuan3Dv2Conditioning`（要 `clip_vision_output`）+ `VAEDecode` + `SaveGLB` | 本机 ckpt：`hunyuan_3d_v2.1`、`hunyuan3d_dit_fp16`、`hunyuan3d_vae_fp16` |
| `stableaudio_sfx` 音效 | `ConditioningStableAudio` + 采样器 + `VAEDecodeAudio` + `SaveAudio` | 一条音效一个 seed，循环音效要标 loop |
| `acestep_music` 音乐 | `EmptyAceStep1.5LatentAudio` + ACE-Step 节点 | 时长控制用 `seconds` |
| `h3_video` gameplay 视频 | `MiniMaxH3EasyLoader`（fl2va/ref2va/text_encoder/video_vae/audio_vae）+ `MiniMaxH3Easy` 或一把梭的 `H3OneNode` | 10–15s、1080P、竖改横都在 `mode`/`aspect_ratio` |

建工作流的顺序建议：先 `zimage_t2i`（最快看到图），再 `birefnet_cutout`，再 `hunyuan3d_i23d`
（这条最容易卡在条件节点的输入类型上），最后音频和 H3（H3 一条要几分钟，先小分辨率试）。

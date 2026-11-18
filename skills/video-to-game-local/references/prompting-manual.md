# 提示词手册（MOSS / H3 image / H3 video / Ignis gpt-image）

> 为什么有这本手册：我们连着踩了三个坑——三模型出图**趋同平均**、H3 视频**欠曝**、竖井**过饱和**。
> 查完官方文档才明白：**这些模型不脑补**。你不写光，它们就给你"没有光"；你不写材质，它们就给你"塑料"。
> 这本手册把"该写什么、写给谁看"固定下来。**写提示词之前先读第 1、2 节。**

## 0. 语言：先用中文（2026-11-16 实测）

> 用户给的判断："H3 / H3 image / Z-Image / MOSS / gpt-image 都支持中文，用中文可能更准。" 实测成立。

同一场景、同一套布光数值、同一 seed，中英各一张：

| 模型 | 语言 | 饱和 | 对比 | 高光 | 细节 | 熵 | 变化 |
|---|---|---|---|---|---|---|---|
| H3 image | 英文 | 0.268 | 160.0 | 0.031 | 0.0266 | 4.27 | — |
| H3 image | **中文** | 0.312 | 167.9 | **0.040** | **0.0293** | 4.31 | 细节 +10%、高光 +29%（光更"实"） |
| MOSS | 英文 | 0.344 | 98.0 | 0.007 | 0.0257 | 3.86 | — |
| MOSS | **中文** | 0.310 | **118.5** | 0.007 | **0.0298** | **4.08** | 对比 +21%、细节 +16%，且不再过饱和 |
| Ignis gpt-image | 英文 | 0.060 | 115.4 | 0.005 | 0.0335 | 4.16 | 出了灰图 |
| Ignis gpt-image | **中文** | **0.156** | 103.8 | 0.006 | 0.0333 | 3.95 | 饱和 +160%，不再是灰图 |

**结论**：三家都是"中文 ≥ 英文"，且都朝着我们要的方向走（更多细节、更多光、少一点灰）。
所以本项目的默认写法是 **中文为主**，技术名词后面加英文括号，避免歧义：

```text
体积雾（volumetric fog，消光系数 extinction 0.04/m）、粗糙度（roughness 0.85）、
金属度（metalness 0.6）、次表面散射（subsurface scattering，半径 2–3 mm）、
基于物理的渲染（physically based rendering，能量守恒 energy-conserving）、
曝光充足（well exposed，中间调可读 readable midtones）
```

三种例外仍用英文：
1. 画面里要出现**英文字**时（照抄原文）；
2. 提示词里要引用官方英文术语表/风格名（如 `anamorphic`）时；
3. 需要和上游 gallery 的英文提示词对齐比较时。

**一个测量噪音要排掉**：H3 中文那一次跑了 253 s，英文只要 10 s——这不是语言慢，
是中间插了 MOSS，把 H3 的权重挤出了显存，重装模型花了 4 分钟。**耗时差异不能当语言效果的证据。**

## 1. 三条铁律

1. **光要写成物理量。** 位置（相对主体的方位/高度）、方向、强度（相对或 EV）、色温（K 或 hex）、
   软硬（硬光/柔光/面积大小）、衰减（随距离）。缺任何一项，模型都会给最保守的平均值。
2. **材质要写成物理属性。** 基础色、粗糙度、金属度、透射、次表面散射、各向异性、脏污。
   "realistic" 是形容词，"roughness 0.8, metalness 0.1, dust film on top" 才是可执行的指令。
3. **镜头要写成参数。** 焦段/视场、机位高度、俯角、距离、运动（轨道/推进/固定）。
   "cinematic" 不是镜头，"35 mm lens at chest height, 12° down-tilt, slow lateral dolly" 才是。

**推论**：同一句笼统提示词喂给 MOSS 和 H3，出来的东西会**像同一张平均图**——这不是模型笨，是我们的输入没有信息量。

## 2. 光段落模板（可直接抄，按场景改数值）

```text
Lighting:
- Key: a single 3 m long fluorescent tube on the ceiling, 2 m to camera-left and 4 m ahead of the subject,
  cold green 4800 K, hard-edged because the tube is narrow, inverse-square falloff, illuminance about 40 lux at the subject.
- Practical (in frame): two more tubes further down the platform, still lit, sickly green (#7fbf7a), 15 lux, flickering at 2 Hz.
- Fill: none from the front; bounce only from the concrete floor 3 m below, 5% of key.
- Rim: cold blue spill from the far tunnel opening, 5° above the horizon line, 10 lux.
- Atmosphere: dry dust in the air, 3 g/m³, visible as a light shaft through the key; visibility 25 m.
- Exposure: well exposed, readable midtones, shadow detail retained, no crushed blacks, no clipped highlights.
```

写作顺序建议：**key → practical（画面里看得见的灯）→ fill → rim → 雾/介质 → 曝光**。
H3 与 MOSS 都吃这种"分项写"的段落；gpt-image 更吃连贯的一段话，把上面各项揉成 2–3 句即可（见 5.4）。

## 3. 材质与渲染术语表（照抄就有用）

| 想要 | 就这么写 |
|---|---|
| 物理正确 | physically based rendering, energy-conserving, measured albedo, correct Fresnel |
| 粗糙混凝土 | albedo #6b6259, roughness 0.85–0.95, metalness 0.0, aggregate speckle, chipped edges |
| 锈蚀钢 | base #7a4a32, roughness 0.6–0.75 with patchy 0.3, metalness 0.6, orange rust flakes over cold grey steel |
| 被能量武器熔过的金属 | melted then re-solidified metal, dark blue oxide tint #2a3b4d, torn rim, micro-cracks |
| 干粉尘 | dry powder layer 2–5 mm, albedo #c9c6bd, no specular, soft footprint shapes |
| 雾/介质 | volumetric fog, single scattering, extinction 0.04 /m, light shaft visible |
| 皮肤（人形时才需要） | subsurface scattering radius 2–3 mm, warm scattering, no waxy sheen |
| 玻璃/冷冻舱 | transmissive glass, IOR 1.5, frosted interior, faint internal glow #a8d8e8 |
| 生物荧光 | weak emissive #7fa88a at 0.15 intensity, glow only in shadow, no neon |
| 运动 | 180° shutter, motion blur on the foreground only |
| 景深 | 35 mm at f/2.8, focus on the subject's head, background soft |

**反面清单**：`8K, best quality, masterpiece, ultra detailed, trending on artstation` —— 这些在 MOSS/H3 上
几乎只增加"塑料感"，官方 tag 顺序里质量词只放最前一个（MOSS）或不写（H3）。

## 4. 各模型的手册（官方口径，别再猜）

### 4.1 MOSS-Image（本地主力打样）

官方 USERGUIDE（<https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md>）：

| 项 | 值 |
|---|---|
| 分辨率 | 总像素 **1M / 1.5M / 2M**；可外推到 0.25M–4M；**宽高必须是 16 的倍数** |
| 步数 | **≥ 50**（快档 25 会掉细节） |
| CFG | **3.0**（3–6；提示词短时往上加） |
| 采样 | **euler**，shift 5.0 |
| SLG | 开；两遍采样 SLG 建议 **skip layer 22**（22/24/26 都行）；**关掉会更"写实"但细节易塌** |
| 语言 | **英文**最优，中文可 |
| 负面词 | 固定五个：`nsfw, worst quality, bad anatomy, watermark, jpeg artifact` |
| tag 顺序 | Quality → Score → Meta → Year → Character → Series → Artist → General |
| 文字 | 要打印的字**用引号**；控制断行直接写 `\n` |
| Layout | JSON：`bbox_format: yxyx`、`bbox_coord_space: abs_centralized`（画布中心为原点、像素绝对值） |

MOSS 的强项是**文字与排版**，弱项是"给你自己想光"。所以喂 MOSS 时必须把第 2 节的光段落整段给它，
否则永远是平光。

### 4.2 H3 image（本地，首选画质）

ComfyUI 里的 `MiniMaxH3ImageConditioning` 是 6 步蒸馏模型，官方模板 `image_minimax_h3_image_t2i`：

| 项 | 值 |
|---|---|
| 采样 | **euler + simple、6 步、CFG 1.0、denoise 1.0**（别改，改了会崩） |
| 尺寸 | 模板默认 **3104×3104**；官方说明低分辨率效果差（4MP 起） |
| 提示词 | 英文长句可以；**CFG 1 没有负分支 → 不要写负面词**，负面词会被当成内容处理 |
| 参考图 | `images` 可选：给图就是编辑/参考（提示词里用 `<Picture 1>` 指代） |

**因为无负分支**，"别太暗"这种话没用；要写"well exposed, readable midtones, key light 40 lux"。

### 4.3 H3 video（本地，参考片段）

官方 prompt guide（<https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md>
与 ComfyUI 的配套说明）：**H3 要的是"分镜时间线"，不是一段散文**。

固定三字段：

```text
integrated_multimodal_description: [Shot 1] <画面 + 动作 + 镜头 + 台词/音效>
overall_soundscape: <环境声、动作声、非语言人声，1–4 句；真静音写 N/A>
non_diegetic_music: <观众能听见、角色听不见的配乐，1–3 句；没有写 N/A>
```

- `[Shot 1]` 从 0.00 s 开始；换镜写 `[Shot 2] At 00:03.500, the camera cuts to ...`（单一时间点，不写区间）。
- 镜头、光、动作、音效写在**同一个 shot 块**里；`length` = 帧数 @24 fps，必须 **17k+5**（默认 124 ≈ 5 s）。
- 原生 **1344×768**，宽高 **32 的倍数**。
- 对白写在 `<d>` 标签里；画面上的文字用英文双引号逐字给出。
- **不要写负面清单**（理由同上：cfg 1 无负分支）。
- 想要"读得清"就写 `well exposed, readable midtones`；想要"暗但有层次"就写 `low-key but readable, shadow detail 保留`。

我们之前 5 条参考片段里 3 条欠曝/过饱和，就是因为只给了散文式描述、没给分镜与光。

### 4.4 Ignis gpt-image（云端，会脑补，擅长"摄影指导"式描述）

来自 `FeiTuPrj_H3/Docs/IMGFLOW_04_Ignis.md` 的官方哲学：

- 把提示词当成**给摄影师的活儿**：一两句连贯的话，说清主体 + 动作/状态 + 环境 + **光线** + 相机/画风。
- **禁**：质量词咒语（8K/best quality）、逗号 tag 流、权重括号、negative 思维（只有 midjourney 吃 tag 流）。
- 编辑：只说"改什么 + 保什么"，不复述整图。
- 它脑补能力强 → 可以给更"氛围向"的引导（"像 90 年代胶片在雨夜拍的地铁站"），但**关键光位仍要写**。

## 5. 四段可复制的骨架（本项目专用）

### 5.1 站台（H3 image / MOSS 通用，英文）

```text
Side-view environment concept, physically based rendering, energy-conserving.
Subject: a ruined underground metro platform; hundreds of destroyed wheeled and tracked combat robots
lie on their sides, torsos punched through by energy weapons, rims melted then solidified with a dark blue
oxide tint (#2a3b4d), torn metal edges, micro-cracks. Dry grey-white dust (#c9c6bd) 2–5 mm thick covers
the anti-slip tiles; chipped tile edges; heavy concrete pillars.
Lighting: one 3 m fluorescent tube on the ceiling 2 m camera-left of frame centre, cold sickly green
4800 K (#7fbf7a), 40 lux at the floor beneath it, hard-edged, inverse-square falloff; two more tubes
further down the platform at 15 lux with a 2 Hz flicker; no frontal fill, 5% bounce from the concrete floor;
cold blue spill from the far tunnel mouth, 10 lux. Volumetric haze, extinction 0.04 /m, a visible light shaft
under the key tube.
Camera: 35 mm equivalent, lens at 1.6 m height, 8° down-tilt, slow lateral dolly, subject centred.
Exposure: well exposed, readable midtones, shadow detail retained, no crushed blacks, no clipped highlights.
No characters.
```

> 与旧版的差别：旧版写的是"a few ceiling tubes glowing sickly green"——没有位置、强度、色温、衰减。
> 模型只能给平均结果。

### 5.2 隧道 / 5.3 竖井 / 5.4 终点

同样四段：Subject / Lighting / Camera / Exposure。竖井的重点是把"扫描锥"写成**一束可见体积光**
（`a visible cone of green light, 5° half-angle, sweeping 12° per second, lit dust inside the cone`），
而不是"scanning light"。

### 5.5 H3 video 骨架

```text
integrated_multimodal_description: [Shot 1] A side-view of a ruined underground metro platform, physically based
rendering, energy-conserving. A 1.2 m segmented worm crawls left-to-right across grey-white dust, body rippling,
each ring lifting and settling. Key light: one ceiling fluorescent tube 2 m ahead, cold sickly green 4800 K,
40 lux, hard-edged, light shaft visible in the volumetric haze; total visibility 25 m; exposure well exposed with
readable midtones. Camera: 35 mm equivalent, 1.6 m height, 8° down-tilt, slow lateral dolly tracking the worm.
overall_soundscape: dry grit crunching under a soft segmented body, a distant electrical hum with a 2 Hz flicker
buzz, faint metallic ticking as dust falls on hollow metal.
non_diegetic_music: a low sustained drone with a slow beating pulse, no melody.
```

## 5.6 实测：手册到底改变了什么（2026-11-16）

同一场景、同一句笼统提示词 vs 第 5.1 节的分项手册提示词，各跑一张：

| 版本 | 饱和 | 对比 | 高光 | 细节 | 熵 | 判断 |
|---|---|---|---|---|---|---|
| h3 扁平 | 0.152 | **217.6** | **0.126** | 0.0276 | 4.62 | 对比过头、高光快炸 |
| **h3 手册** | 0.268 | 160.0 | 0.031 | 0.0266 | 4.27 | **全部落进 SPEC 区间** |
| moss 扁平 | 0.199 | 107.0 | 0.002 | 0.0253 | 4.03 | 平、没有光 |
| moss 手册 | **0.344** | 98.0 | 0.007 | 0.0257 | 3.86 | 光出现了，但绿过了（超 0.28 上限） |

三条结论：
1. **分项写光真的管用**：H3 的高光从 0.126 收到 0.031、对比从 218 收到 160，同时把"光"落成了看得见的光斑。
2. **写 hex 就等于调色**：两家饱和都涨了 0.11–0.15，因为 `#7fbf7a` 被当成了真实色值。想要克制就把色值写淡
   （`pale green #9fb79a`）并补一句 `the walls stay neutral grey, only the tubes are green`。
3. 两家的"平/爆"分工没变：H3 依旧容易爆高光（所以更该写曝光与光强），MOSS 依旧不会自己给光（所以更该写光源）。

对照图：`games/pingchuan-rail/look/compare_manual_vs_flat.jpg`。

## 6. 写完自查（12 条）

1. 光写了 key 的位置/方向/色温/强度/软硬/衰减吗？
2. 画面里"看得见的灯"写了吗（practical）？
3. 有没有 fill / rim / bounce？还是只有一盏灯？
4. 雾/介质写了**浓度**吗（extinction 或 visibility）？
5. 材质写了 roughness / metalness 吗？
6. 需要透光/散射/次表面反射的材质，写清了吗？
7. 镜头写了焦段、高度、俯角、运镜吗？
8. 曝光写了 "well exposed / readable midtones" 吗？
9. 模型特定的坑避开了吗（MOSS：步数≥50、16 倍数；H3：无负面词、17k+5 帧）？
10. 负面词只在 MOSS（固定五个）与 Ignis 的惯例里出现，H3 一律不写。
11. 有没有"质量咒语"（8K/best quality）？有就删。
12. 英文写了吗？（两者英文都最稳）

## 7. 出处（按可信度分层，遵守搜索指南）

**官方一手**
- MOSS-Image USERGUIDE：<https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md>
- MiniMax H3 视频提示词指南：<https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md>
- MiniMax H3 仓库与 skills：<https://github.com/MiniMax-AI/MiniMax-H3>
- Ignis 流程文档（本机）：`FeiTuPrj_H3/Docs/IMGFLOW_04_Ignis.md`

**官方文档（二手整理，但同源）**
- ComfyUI MOSS-Image 教程：<https://docs.comfy.org/tutorials/image/moss-image/moss-image>
- ComfyUI H3 提示词指南：<https://docs.comfy.org/tutorials/video/minimax/minimax-h3-prompt-guide>

**社区（只当线索，未采信为规则）**
- MOSS-Image prompting guide（HF blog）：<https://huggingface.co/blog/showmakerai/moss-image-prompting-guide>
- r/StableDiffusion 的 MOSS / H3 提示词帖
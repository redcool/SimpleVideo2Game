---
name: audio-taste
description: >-
  Turn "does this sound right?" into numbers. Measures loudness (LUFS), peak and true peak,
  silence ratio, brightness proxy and loop seam of any clip, then judges it against a stated
  profile (sfx / music / loop). 把音频验收量化的通用技能：响度、削顶、静音、接缝，
  一次命令给出"能不能进游戏"的结论。Use when generated sound effects or music must be checked
  before they go into a game, a video, or any mix where the level actually matters.
license: MIT
metadata:
  scope: 与项目无关，任何"出音频"的库都可以装
  pair: 与 skills/visual-taste 对称（图片看数字，音频也要看数字）
---

# Audio Taste（音频量化验收）

**问题**：生成的音效"能听见但没用"——削顶、整体太轻、循环首尾接不上导致咔哒。
这些要靠肉耳听很多遍，用三个数字一秒就能看出来。

**本技能**：用 ffmpeg 的标准滤镜（`astats` / `ebur128` / `silencedetect`）量五个指标，
按档位给结论。不做自研 DSP，不引第三方包。

## 指标

| 指标 | 来源 | 说明 |
|---|---|---|
| `peak_db` / `true_peak_db` | astats / ebur128 | 峰值与真峰。**≥ −1 dB 就是削顶** |
| `lufs_integrated` | ebur128 | 整体响度（LUFS-I）。游戏音效约 −16，音乐约 −18 |
| `loudness_range_lu` | ebur128 | 动态范围（LRA）。太扁＝垫底噪音 |
| `silence_fraction` | silencedetect | 静音占比（−50 dB，>100 ms 才算） |
| `seam_db` / `seam_jump` | 整段解码（**原生采样率**）后比较首尾 | 循环接缝：首尾 100 ms 能量差、接缝处样本跳变 |

## 四个档位（起步阈值，按项目校准）

| 档位 | 峰值 | 响度 | 时长 | 其他 |
|---|---|---|---|---|
| `sfx` 单次音效 | ≤ −1 dBFS | **−26 ~ −13 LUFS** | 0.2–10 s | 静音 < 60% |
| `music` 音乐 | ≤ −1 dBFS | −21 ~ −15 LUFS | 2–300 s | LRA ≥ 2 LU |
| `loop` 循环音效 | ≤ −1 dBFS | −24 ~ −12 LUFS | 0.5–60 s | 接缝能量差 ≤ 6 dB 且跳变 ≤ 0.15 |
| `drone` 环境铺底 | ≤ −1 dBFS | −24 ~ −14 LUFS | 5–300 s | **不要求 LRA**（铺底音本来就该是平的） |

**为什么 sfx 上限是 −26 而不是 −19**：1 秒的瞬态（落地、火花）峰值顶到 −1.5 dBTP 之后，
响度往往只能到 −19 ~ −26 LUFS；为了追 −16 而抬增益会直接削顶。瞬时音效在混音里靠**峰值**被听见，
不靠 LUFS。别为了数字牺牲峰值。

## 用法

```powershell
python skills\audio-taste\scripts\audio_report.py assets\sfx_crawl.wav
python skills\audio-taste\scripts\audio_report.py assets\sfx_hum.wav --profile loop --loop-seam
python skills\audio-taste\scripts\audio_report.py take.mp4 --profile music --json
python skills\audio-taste\scripts\audio_report.py sfx.wav --strict     # 不合格返回 1，可进门禁
```

视频也能测（自动取音轨）。依赖：ffmpeg / ffprobe。

## 修法（按指标对症）

| 不合格 | 怎么修 |
|---|---|
| peak ≥ −1 | 整体降增益；或 `alimiter` 软限幅；别用硬削 |
| 响度太低（如 −29 LUFS） | `loudnorm=I=-16:TP=-1.5` 归一化 |
| 静音太多 | 生成时加 `duration` 或换描述；后期静音裁剪 |
| 循环接缝大 | 用 audio_fix.py --profile loop（首尾交叉淡化 + 静态增益）；或重新生成并要求 loop |
| LRA 太扁 | 加起伏/层次，别当垫底噪音 |

## 可选后端：earshot

[earshot](https://github.com/Leonxlnx/earshot) 是「给 agent 的耳朵」：语义描述（像什么声音）、按描述排序、
长录音里找最佳片段、真假录音判别、整片听感时间线、标注 PNG、专业预告片评分卡。它更强，
但需要 **CPU 版 torch + CLAP 模型**，所以**不装进本仓库 venv**（AGENTS 硬规则：venv 不装 torch）。

装上之后（自己独立环境）本技能可以直接用：

```powershell
python skills\audio-taste\scripts\earshot_bridge.py doctor                 # 探测
python skills\audio-taste\scripts\audio_report.py x.wav --earshot          # 报告里多一段 earshot 客观测量
python skills\audio-taste\scripts\audio_report.py x.wav --earshot-describe # 再加语义描述（慢）
```

找不到时**不影响主流程**，只打一行安装提示。⚠️ PyPI 上的 earshot 是另一个包（VAD），
要用 `uv tool install earshot @ git+https://github.com/Leonxlnx/earshot` 或 clone 后装。

## 什么时候别用它

- 不要用数字代替听感：这些指标保证"能听清、不炸、能循环"，不保证"好听"。
- 不要跨类型比响度：UI 提示音和战斗音效的正确区间不一样。
- 不要把 LUFS 当音量旋钮：游戏里还有总线与场景混音。

## 出处

ffmpeg 滤镜文档：`astats`、`ebur128`、`silencedetect`、`loudnorm`（ffmpeg.org/ffmpeg-filters.html）。
阈值来自本项目的实测（见 `games/pingchuan-rail` 的音效报告），不是广播标准。
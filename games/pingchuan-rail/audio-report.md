# 音频体检报告（audio-taste）

> 由 skills/audio-taste/scripts/audio_report.py 生成；指标来自 ffmpeg 的 astats / ebur128 / silencedetect。
> 重新生成：python tmp/audio_audit.py，或直接对单个文件跑 audio_report.py。

| 资产 | 档位 | 时长 | 峰值 dBFS | 响度 LUFS | LRA | 静音占比 | 接缝 dB / 波形差 | 结论 |
|---|---|---|---|---|---|---|---|---|
| sfx_crawl | sfx | 4.0 s | 0.0 | -29.0 | 1.4 | 0.0 | — | ❌ peak_db、lufs_integrated |
| sfx_launch | sfx | 2.0 s | 0.0 | -16.6 | 0.0 | 0.0 | — | ❌ peak_db |
| sfx_tube_hum | loop | 6.0 s | -11.01 | -23.4 | 0.4 | 0.055 | 99.0 / 0.4044 | ❌ seam_db、seam_mismatch |
| clip: ref_station | music | 5.167 s | -3.84 | -13.4 | 0.2 | 0.0 | — | ❌ lufs_integrated、loudness_range_lu |
| clip: ref_tunnel | music | 5.167 s | -0.79 | -13.1 | 0.3 | 0.0 | — | ❌ peak_db、lufs_integrated、loudness_range_lu |

## 怎么修

- 峰值 >= -1 dBFS：整体降增益，或用 alimiter 软限幅。
- 响度偏低（如 -29 LUFS）：用 loudnorm=I=-16:TP=-1.5 归一化。
- 循环接缝大：首尾 50-100 ms 交叉淡化，或重新生成并要求 loop。
- 动态太扁（LRA < 2）：加起伏，别当垫底噪音。

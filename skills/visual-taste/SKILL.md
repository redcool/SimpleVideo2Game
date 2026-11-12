---
name: visual-taste
description: >-
  Turn "does it look right?" into numbers and side-by-side pictures. Measures palette
  concentration, saturation, contrast, tonal zones, detail density and subject/background
  hierarchy of any still or clip, judges them against a stated profile, and pairs a
  reference with a result at the same fixed moments. 把审美量化的通用技能：配色报告、
  单帧结构指标、并排对比图、录像最活窗口。Use when comparing AI images, generated video,
  game screenshots or renders against a reference, or when a look must be matched instead
  of described with adjectives.
license: MIT
metadata:
  upstream: lovisdotio/video-to-game (MIT) — look-and-post.md, study_video.py, side_by_side.py, best_window.py
  scope: 与项目无关，任何"出图/出视频"的库都可以装
---

# Visual Taste（审美量化）

**问题**：所有人都会说"再精致一点"，没人说得清差在哪，于是只能反复抽卡看运气。

**本技能的做法**：把画面拆成几个能测的数（主色占比、艳度、对比、明暗分区、细节量、主体/背景差异），
每次只改一项，都拿**同一位置的并排图**和同一组数字对比。审美仍然由人判断，但判断有据可依、可复现。

## 三条硬规则

1. **先写规格，再动手。** 规格里必须有数字：主色 hex、雾起止距离、bloom 强度、暗角、颗粒、
   曝光与色调曲线。见 `references/look-spec.md`。没有数字的"电影感"等于没写。
2. **同一位置比。** 每次都在**同样三个点**（起点 / 关键瞬间 / 远处）出并排图；
   换位置比等于用运气冒充进步。见 `references/compare-routine.md`。
3. **一次只改一项。** 改完立刻复测，数字往回走就说明改错了方向。一次改五项，等于什么都不知道。

## 能测什么

| 指标 | 人话 | 安静档起步区间 | 偏了通常意味着 |
|---|---|---|---|
| `mean_saturation` | 平均艳度 | 0.12 – 0.45 | 偏低＝发灰没精神；偏高＝荧光、抢戏 |
| `palette_concentration_top5` | 前 5 个主色占比之和 | 0.45 – 0.92 | 偏低＝杂、没有主调；偏高＝单调 |
| `contrast_p95_minus_p5` | 对比（亮部与暗部差） | 30 – 110 | 偏低＝灰雾；偏高＝黑死白炸 |
| `shadow/mid/highlight_fraction` | 暗/中/亮区占比 | 暗 0.05–0.55；亮 0.02–0.35 | 三段失衡＝画面压不住或飘 |
| `pure_black+white_fraction` | 纯黑纯白像素 | < 0.06 | 偏高＝断层、贴片感 |
| `luma_entropy_bits` | 亮度分布有多散 | 2.5 – 4.8 | 偏低＝平；偏高＝碎 |
| `edge_density` | 平均梯度（细节量） | 0.006 – 0.045 | 偏低＝空/糊；偏高＝噪、抢注意力 |
| 层次（需主体框） | 主体区与背景的亮度/饱和度差 | 亮度差 ≥ 25 或饱和度差 ≥ 0.15 | 不达标＝主角陷进背景 |

阈值是**起步值**，按项目风格校准，改的是脚本顶部那一张表，不是心里的标准。
定义、公式与校准方法见 `references/metrics.md`。

## 四个工具

```powershell
# 1) 配色报告（图或视频；给结论，不吹）
python skills\visual-taste\scripts\palette_report.py shot.png
python skills\visual-taste\scripts\palette_report.py gameplay.mp4 --samples 8 --profile vivid --json

# 2) 结构指标 + 层次检验（主体框：左,上,宽,高，统计坐标系 320 宽）
python skills\visual-taste\scripts\frame_metrics.py shot.png --subject-box 110,60,100,90

# 3) 并排图：左参考、右成品，同样三个时间点
python skills\visual-taste\scripts\side_by_side.py 参考.mp4 成品.mp4 -o pairs --times 2,5,8

# 4) 录像挑"最活的几秒"（分数只说明有动静，务必看帧）
python skills\visual-taste\scripts\rank_take_window.py take.mp4 --length 3 --top 3
```

四个工具都只依赖 Python 3.11+ 与 ffmpeg，不加第三方包，可以原样装进任何库。

## 工作流

1. **量参考**：`palette_report.py 参考.mp4` 拿到参考的主色与区间，抄进规格。
2. **生成/渲染**：用本项目自己的产线出图（本仓库是 ComfyUI）。
3. **量成品并比差值**：`--baseline 参考.json`，看 `差` 的方向，比看绝对区间可信。
4. **并排看**：`side_by_side.py` 在三个固定点出图，看图说话，别看数字说话。
5. **只改一项**：先改影响最大的（通常是配色与对比，然后是细节量，最后是构图）。
6. **复测并记录**：把两次的数字写进项目的验收记录里，别靠记忆。

## 什么时候别用它

- **不要用数字代替判断**：指标全绿也可能难看（构图、故事、可读性不在指标里）。
- **不要拿并排图当单帧量**：并排图是两个世界 + 白边，先切半再量。
- **不要跨风格比数字**：水墨动画和霓虹赛博的"正确"区间不一样，比之前先对齐档位。
- **不要为过门槛而调参**：把饱和硬拉到 0.12 只会得到一张灰图。数字是发现问题的灯，不是终点。

## 出处

`side_by_side.py`、`rank_take_window.py` 改编自上游
[lovisdotio/video-to-game](https://github.com/lovisdotio/video-to-game)（MIT）；
指标口径参考其 `references/look-and-post.md` 与 `scripts/study_video.py` 的调色板统计。
`palette_report.py`、`frame_metrics.py`、`visual_metrics_core.py` 为本仓新增。
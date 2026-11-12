# games/

每个游戏一个目录，产物都在这里；`assets/`、`takes/`、`study/`、`pairs/` 不入库（见 `.gitignore`）。

```text
games/<game>/
├── README.md            概念、操作、素材清单（来自 assets/asset_log.json）、成本 0、与视频的差异
├── video/               源 gameplay 视频（不入库）
├── study/               study_video.py 的产物：帧、sheet.jpg、study.json —— 入库 study.json 与 sheet.jpg
├── SPEC.md              写代码前必须先写的设计规格（机位/主角/机制/关键瞬间/世界/用色）
├── assets/              本地 ComfyUI 生成的素材 + asset_log.json（素材不入库，日志入库）
├── game/index.html      Three.js，单文件优先；`?autostart`、`?seed=N`、`window.__game` 契约必须有
├── pairs/               side_by_side.py 出的并排图，至少三张：起点 / 关键瞬间 / 远处
└── takes/               record_play.mjs 的录像（不入库），README 里写用哪一段
```

一个游戏"做完了"的判据（和上游一致）：

- 三个固定位置都有"视频 | 游戏"并排图，且缩略图大小下看不出明显不是同一个世界；
- 一段录像里没有坠落、卡墙、死秒钟、标题字盖脸，关键瞬间在画面中心；
- 控制台 0 错误，笔记本 60 fps（或 30 fps 但画面明显更好）；
- README 老实列出和视频的差异，不写"完全一致"。

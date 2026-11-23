# 外部项目评估（prior art）

记录我们**评估过**、并明确**采纳 / 拒绝**了什么。目的是避免重复评估，也避免「抄了却不知道为什么」。

---

## 1. WhiteTowerAI/ohmygame — 开源的一人游戏工作室（2026-11-16 评估）

**它是什么**：Electron 桌面应用（mac/Windows）。左边聊天、右边跑游戏；agent 写设计稿 → 写代码 →
在实时预览里跑 → **自己玩一遍** → 出错就改 → 发布成链接（带多人房间、存档、排行榜）。
资产画布统一管图片/视频/3D/动画/配音/音效/音乐。插件覆盖 Godot、Unity、Unreal、Blender、Aseprite、
Tiled、微信与抖音小游戏。**明确支持 DeepSeek Harness（dsh）作为外部 MCP 客户端。**

**结论：不采纳为工具，采纳三条设计。**

| 维度 | 它 | 我们 | 判定 |
|---|---|---|---|
| 素材生成 | 走已配置的 provider（自带 key、按量计费） | 本机 ComfyUI，零 API 费用 | ❌ 与「素材只从本机出」直接冲突 |
| 运行形态 | 必须开桌面 app（game_use 要 app 和游戏预览窗口） | node tests/smoke_game.mjs 无头浏览器 | ❌ 不能进 CI，我们的更轻 |
| 发布 | 一键发链接 + 多人、存档、排行榜 | 本地静态站 | 暂不需要 |
| 工程纪律 | 公开工具表固定且版本化，改工具名算破坏性变更，测试断言工具名单 | check_repo.py 断言必需文件与工作流 | ✅ 同一套思路，互相印证 |
| 长任务模型 | 生成工具最多等 **45 s**，没完就返回 **job id**，再 wait_job | 一次阻塞等待 + 超时（撞到过 600 s 墙钟被杀） | ✅ **值得抄** |
| 参数透明 | 模型不支持的参数回一行 Not applied，并把项列进 ignored；拼错的进 unknownFields | --set 写错参数名只会静默无效 | ✅ **值得抄** |

**要抄的三条**

1. **长生成 job 化**：与其「阻塞等到超时被杀」，不如「提交 → 拿 id → 另起一次查询与下载」。
   我们的 comfy_asset.py 目前是阻塞式；待办：加 --detach（提交并打印 prompt_id）与 --collect <id>（事后取回）。
   背景：一次 H3 视频生成撞上调用方 600 s 上限被截断，成品在 ComfyUI 里但客户端已死。
2. **参数透明**：--set 命中的节点与参数必须回显实际生效清单，未识别的键要显式报错或列进 ignored，
   而不是静默无效（踩过：给 H3 写负面词、给不支持 width 的工作流传尺寸）。
3. **公开契约固定**：工作流文件名与节点 id 就是我们的公开工具表，改名要走版本化加测试断言。

---

## 2. Leonxlnx/earshot — 给 agent 的耳朵（2026-11-16 评估）

**它是什么**：本地 CPU 的音频理解工具（CLI / Python API / MCP）。describe（像什么声音）、
match（描述匹配度）、find（长录音找最佳片段）、timeline（整片听感时间线）、sheet（标注 PNG）、
critique（对照专业预告片评分）、forge（用代码造音效并自我迭代）。

**结论：采纳为可选后端。** 需要 CPU 版 torch + CLAP 模型，**不装进本仓库 venv**（纪律：venv 不装 torch），
用 skills/audio-taste/scripts/earshot_bridge.py 桥接；找不到只提示、不影响主流程。
⚠️ PyPI 上的 earshot 是另一个包（VAD），正确装法见 SKILL。

---

## 3. redcool/SimpleMcpServer — 规则枢纽与引擎桥（本仓库的规则真源）

139 个工具：blender.*（64）、blender2.*（28）、unreal.*（34）、memory.*（10）、bridge.*（2）、web.*（1）。
**bridge.list 当前为空**（没有引擎在线），所以 3D 预处理走 Blender CLI 无头模式；
桥接上线后可改用 blender.execute_blender_code 做需要交互状态的操作。

---

## 4. lovisdotio/video-to-game — 上游原型（只读参考 _ref/）

7 步工作流 + fal 付费素材线的原始版本。我们的差异：素材线换成本机 ComfyUI、加了
visual-taste 与 audio-taste 两套量化验收、并补了它完全没有的音频分析环节。

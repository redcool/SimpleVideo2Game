"""video2game-local 的实现层。

分层约定（纪律）：
- command_line       命令行，只解析参数与错误出口
- pipeline_orchestrator  唯一跨模块调度处
- comfy_bridge / video_study / playtest_capture  单一职责的模块
- common             路径与日志等共用工具
"""

"""ComfyUI 的 HTTP 客户端：只负责"发请求、收 JSON"。

刻意只用标准库：资产桥不需要第三方包，这样技能可以原样搬到别的机器，
也不会把 GPU 依赖（torch）拖进本仓库的 venv。
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import uuid

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:8188"


class ComfyRequestError(RuntimeError):
    """服务端拒绝请求，或服务不可达。"""


class ComfyHttpClient:
    """一个 ComfyUI 实例的最小客户端。"""

    def __init__(self, base_url: str | None = None, client_id: str | None = None, timeout_seconds: float = 30.0) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.client_id = client_id or uuid.uuid4().hex
        self.timeout_seconds = timeout_seconds

    def _send(self, path: str, payload: dict | None = None, method: str | None = None, raw: bool = False):
        url = self.base_url + path
        body = None
        headers: dict[str, str] = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:2000]
            raise ComfyRequestError(f"{method or 'GET'} {path} -> HTTP {error.code}: {detail}") from None
        except urllib.error.URLError as error:
            raise ComfyRequestError(
                f"连不上 ComfyUI（{self.base_url}）：{error.reason}。它启动了吗？"
            ) from None
        return content if raw else json.loads(content.decode("utf-8"))

    def get(self, path: str):
        return self._send(path)

    def post(self, path: str, payload: dict):
        return self._send(path, payload=payload, method="POST")

    # ---- 只读查询 ----
    def system_statistics(self) -> dict:
        return self.get("/system_stats")

    def queue_state(self) -> dict:
        return self.get("/queue")

    def model_folders(self) -> list[str]:
        return self.get("/models")

    def model_files(self, folder: str) -> list[str]:
        return self.get(f"/models/{urllib.parse.quote(folder)}")

    def object_information(self, class_name: str | None = None):
        if class_name:
            return self.get("/object_info/" + urllib.parse.quote(class_name))
        return self.get("/object_info")

    # ---- 任务 ----
    def submit_workflow(self, workflow: dict, extra_data: dict | None = None) -> str:
        """提交 API 格式工作流，返回 prompt_id。"""
        if not isinstance(workflow, dict) or not workflow:
            raise ComfyRequestError("工作流必须是非空的 API 格式字典")
        response = self.post("/prompt", {"prompt": workflow, "client_id": self.client_id,
                                         "extra_data": extra_data or {}})
        if response.get("node_errors"):
            raise ComfyRequestError("节点校验失败：" + json.dumps(response["node_errors"])[:2000])
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise ComfyRequestError("提交返回异常：" + json.dumps(response)[:2000])
        LOGGER.debug("已排队 %s", prompt_id)
        return prompt_id

    def history_entry(self, prompt_id: str) -> dict | None:
        return (self.get(f"/history/{urllib.parse.quote(prompt_id)}") or {}).get(prompt_id)

    def download_output(self, filename: str, subfolder: str = "", storage_type: str = "output") -> bytes:
        query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": storage_type})
        return self._send("/view?" + query, raw=True)

    def interrupt(self):
        return self.post("/interrupt", {})

    def free_memory(self, unload_models: bool = True, release_memory: bool = True):
        """释放显存。跑大模型（H3、Qwen-Edit）前先调用，避免抢不到卡。"""
        return self.post("/free", {"unload_models": unload_models, "free_memory": release_memory})

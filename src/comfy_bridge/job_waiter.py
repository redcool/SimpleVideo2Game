"""等待一个 ComfyUI 任务结束。

职责单一：轮询 /history，直到成功或失败。不做下载、不写日志——那些是别人的事。
"""
from __future__ import annotations

import logging
import time

from .http_client import ComfyHttpClient, ComfyRequestError

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 1800.0
DEFAULT_POLL_SECONDS = 1.0


class JobFailedError(RuntimeError):
    """任务在 ComfyUI 里执行失败。"""


def describe_failure(status: dict) -> str:
    """从 history 的 status 里抽出人能读的失败原因。

    ComfyUI 的 messages 是一串事件流；整个塞进报错会让真正的原因淹没在日志里。
    这里只取 execution_error 的 节点类型 / 节点 id / 异常消息。
    """
    for message in status.get("messages") or []:
        if not isinstance(message, (list, tuple)) or len(message) < 2:
            continue
        if message[0] != "execution_error":
            continue
        details = message[1] or {}
        node_type = details.get("node_type", "?")
        node_id = details.get("node_id", "?")
        exception_type = details.get("exception_type", "Error")
        exception_message = str(details.get("exception_message", "")).strip().splitlines()
        first_line = exception_message[0] if exception_message else ""
        return f"节点 {node_id}（{node_type}）{exception_type}: {first_line}"
    return "任务失败，但 history 里没有 execution_error 明细"


def wait_for_completion(client: ComfyHttpClient, prompt_id: str,
                        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
                        poll_seconds: float = DEFAULT_POLL_SECONDS,
                        progress_callback=None) -> dict:
    """阻塞直到任务完成，返回 history 条目。"""
    started_at = time.monotonic()
    while True:
        entry = client.history_entry(prompt_id)
        if entry:
            status = entry.get("status") or {}
            if status.get("completed") or status.get("status_str") in ("success", "error"):
                if status.get("status_str") == "error":
                    raise JobFailedError(f"任务 {prompt_id} 失败 —— {describe_failure(status)}")
                return entry
        elapsed = time.monotonic() - started_at
        if timeout_seconds and elapsed > timeout_seconds:
            raise JobFailedError(f"任务 {prompt_id} 超过 {timeout_seconds:.0f} 秒仍未完成")
        if progress_callback:
            progress_callback(elapsed)
        time.sleep(poll_seconds)
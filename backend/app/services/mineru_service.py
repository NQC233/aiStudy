from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from app.core.config import settings


class MinerUConfigurationError(RuntimeError):
    """MinerU 配置缺失时抛出的异常。"""


class MinerURequestError(RuntimeError):
    """MinerU 请求失败时抛出的异常。"""


@dataclass
class MinerUTaskResult:
    """统一封装 MinerU 任务状态。"""

    task_id: str
    data_id: str | None
    state: str
    trace_id: str | None = None
    full_zip_url: str | None = None
    err_msg: str | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


def _ensure_configured() -> None:
    if not settings.mineru_api_key:
        raise MinerUConfigurationError("未配置 MinerU API Key。")
    if not settings.mineru_base_url:
        raise MinerUConfigurationError("未配置 MinerU Base URL。")


def _request_json(url: str, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_configured()
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    http_request = request.Request(
        url=url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {settings.mineru_api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with request.urlopen(http_request, timeout=settings.mineru_timeout_sec) as response:
            raw_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise MinerURequestError(f"MinerU 请求失败，HTTP {exc.code}：{error_body or exc.reason}") from exc
    except error.URLError as exc:
        raise MinerURequestError(f"MinerU 请求失败：{exc.reason}") from exc

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise MinerURequestError("MinerU 返回了无法解析的 JSON。") from exc


def _extract_task_payload(response_data: dict[str, Any]) -> dict[str, Any]:
    code = response_data.get("code")
    if code not in {0, "0", None}:
        message = response_data.get("msg") or response_data.get("message") or "MinerU 返回非成功状态。"
        raise MinerURequestError(str(message))
    data = response_data.get("data")
    if not isinstance(data, dict):
        raise MinerURequestError("MinerU 返回中缺少 data 字段。")
    return data


def _build_status_url(task_id: str) -> str:
    base_url = settings.mineru_base_url.rstrip("/")
    return f"{base_url}/{task_id}"


def _extract_progress(data: dict[str, Any]) -> dict[str, Any]:
    extract_result = data.get("extract_result")
    if isinstance(extract_result, dict):
        return {
            "extracted_pages": extract_result.get("extract_progress"),
            "total_pages": extract_result.get("total_pages"),
            "start_time": extract_result.get("start_time"),
        }
    return {}


def _to_task_result(response_data: dict[str, Any]) -> MinerUTaskResult:
    data = _extract_task_payload(response_data)
    extract_result = data.get("extract_result")
    if isinstance(extract_result, dict):
        state = str(extract_result.get("state") or data.get("state") or "unknown")
        full_zip_url = extract_result.get("full_zip_url")
        err_msg = extract_result.get("err_msg")
    else:
        state = str(data.get("state") or "submitted")
        full_zip_url = data.get("full_zip_url")
        err_msg = data.get("err_msg")

    task_id = str(data.get("task_id") or data.get("id") or "")
    if not task_id:
        raise MinerURequestError("MinerU 返回中缺少 task_id。")

    return MinerUTaskResult(
        task_id=task_id,
        data_id=data.get("data_id"),
        state=state,
        trace_id=data.get("trace_id"),
        full_zip_url=full_zip_url,
        err_msg=err_msg,
        progress=_extract_progress(data),
        raw_response=response_data,
    )


def submit_parse_task(pdf_url: str) -> MinerUTaskResult:
    """提交 MinerU 解析任务。"""
    payload: dict[str, Any] = {"url": pdf_url}
    if settings.mineru_model_version:
        payload["backend"] = settings.mineru_model_version
    response_data = _request_json(settings.mineru_base_url, "POST", payload)
    return _to_task_result(response_data)


def query_parse_task(task_id: str) -> MinerUTaskResult:
    """查询 MinerU 解析任务状态。"""
    response_data = _request_json(_build_status_url(task_id), "GET")
    return _to_task_result(response_data)


def poll_parse_task(task_id: str) -> MinerUTaskResult:
    """轮询任务直到结束或超时。"""
    deadline = time.monotonic() + settings.mineru_poll_timeout_sec
    latest_result = query_parse_task(task_id)

    while latest_result.state not in {"done", "success", "failed", "error"}:
        if time.monotonic() >= deadline:
            raise MinerURequestError(f"MinerU 解析超时，task_id={task_id}")
        time.sleep(settings.mineru_poll_interval_sec)
        latest_result = query_parse_task(task_id)

    return latest_result


def download_parse_zip(zip_url: str) -> bytes:
    """下载 MinerU 返回的解析压缩包。"""
    try:
        with request.urlopen(zip_url, timeout=settings.mineru_timeout_sec) as response:
            return response.read()
    except error.HTTPError as exc:
        raise MinerURequestError(f"下载 MinerU 结果包失败，HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise MinerURequestError(f"下载 MinerU 结果包失败：{exc.reason}") from exc

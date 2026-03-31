from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class TaskFailureInfo:
    """统一封装任务失败分类结果。"""

    error_code: str
    retryable: bool
    normalized_message: str

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "error_code": self.error_code,
            "retryable": self.retryable,
            "error_message": self.normalized_message,
        }


def _exception_name_chain(exception: Exception) -> set[str]:
    return {cls.__name__ for cls in exception.__class__.__mro__}


def classify_task_exception(exception: Exception) -> TaskFailureInfo:
    """按异常类型统一分类错误码和可重试语义。"""
    names = _exception_name_chain(exception)
    message = str(exception).strip() or "任务执行失败。"

    if names & {
        "MinerUConfigurationError",
        "EmbeddingConfigurationError",
        "ValueError",
        "TypeError",
    }:
        return TaskFailureInfo(
            error_code="input_invalid", retryable=False, normalized_message=message
        )

    if names & {"TimeoutError"}:
        return TaskFailureInfo(
            error_code="timeout", retryable=True, normalized_message=message
        )

    if names & {
        "MinerURequestError",
        "EmbeddingRequestError",
        "ConnectionError",
        "OSError",
    }:
        return TaskFailureInfo(
            error_code="external_dependency", retryable=True, normalized_message=message
        )

    return TaskFailureInfo(
        error_code="internal_error", retryable=True, normalized_message=message
    )


def compute_retry_delay_seconds(
    *,
    attempt: int,
    base_seconds: int,
    max_seconds: int,
    use_jitter: bool,
) -> int:
    """根据重试次数计算指数退避时长。"""
    safe_attempt = max(1, attempt)
    safe_base = max(1, base_seconds)
    safe_max = max(safe_base, max_seconds)
    delay = min(safe_max, safe_base * (2 ** (safe_attempt - 1)))

    if not use_jitter:
        return delay

    jitter_ceiling = max(1, delay // 2)
    return min(safe_max, delay + random.randint(0, jitter_ceiling))


def build_retry_snapshot(
    *, attempt: int, max_retries: int, delay_seconds: int
) -> dict[str, str | int | bool]:
    """构建统一重试观测快照。"""
    next_retry_at = datetime.now(UTC) + timedelta(seconds=max(0, delay_seconds))
    return {
        "attempt": attempt,
        "max_retries": max_retries,
        "next_retry_eta": next_retry_at.isoformat(),
        "auto_retry_pending": True,
    }

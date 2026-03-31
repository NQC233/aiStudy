import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.task_reliability import (
    TaskFailureInfo,
    classify_task_exception,
    compute_retry_delay_seconds,
)


class MinerUConfigurationError(RuntimeError):
    pass


class MinerURequestError(RuntimeError):
    pass


class EmbeddingConfigurationError(RuntimeError):
    pass


class EmbeddingRequestError(RuntimeError):
    pass


class ClassifyTaskExceptionTests(unittest.TestCase):
    def test_marks_configuration_errors_as_non_retryable_input_invalid(self) -> None:
        failure = classify_task_exception(MinerUConfigurationError("missing api key"))
        self.assertEqual(failure.error_code, "input_invalid")
        self.assertFalse(failure.retryable)

    def test_marks_external_request_errors_as_retryable(self) -> None:
        failure = classify_task_exception(MinerURequestError("service unavailable"))
        self.assertEqual(failure.error_code, "external_dependency")
        self.assertTrue(failure.retryable)

    def test_marks_timeout_errors_as_retryable_timeout(self) -> None:
        failure = classify_task_exception(TimeoutError("timeout"))
        self.assertEqual(failure.error_code, "timeout")
        self.assertTrue(failure.retryable)

    def test_marks_unknown_errors_as_retryable_internal_error(self) -> None:
        failure = classify_task_exception(RuntimeError("unexpected"))
        self.assertEqual(failure.error_code, "internal_error")
        self.assertTrue(failure.retryable)

    def test_marks_embedding_configuration_error_as_non_retryable(self) -> None:
        failure = classify_task_exception(EmbeddingConfigurationError("bad config"))
        self.assertEqual(failure.error_code, "input_invalid")
        self.assertFalse(failure.retryable)

    def test_marks_embedding_request_error_as_retryable(self) -> None:
        failure = classify_task_exception(EmbeddingRequestError("remote error"))
        self.assertEqual(failure.error_code, "external_dependency")
        self.assertTrue(failure.retryable)


class RetryDelayTests(unittest.TestCase):
    def test_retry_delay_uses_exponential_backoff_without_jitter(self) -> None:
        self.assertEqual(
            compute_retry_delay_seconds(
                attempt=1, base_seconds=5, max_seconds=120, use_jitter=False
            ),
            5,
        )
        self.assertEqual(
            compute_retry_delay_seconds(
                attempt=2, base_seconds=5, max_seconds=120, use_jitter=False
            ),
            10,
        )
        self.assertEqual(
            compute_retry_delay_seconds(
                attempt=3, base_seconds=5, max_seconds=120, use_jitter=False
            ),
            20,
        )

    def test_retry_delay_respects_max_seconds(self) -> None:
        self.assertEqual(
            compute_retry_delay_seconds(
                attempt=8, base_seconds=5, max_seconds=30, use_jitter=False
            ),
            30,
        )

    def test_failure_info_to_dict_contains_contract_fields(self) -> None:
        failure = TaskFailureInfo(
            error_code="timeout", retryable=True, normalized_message="retry later"
        )
        self.assertEqual(
            failure.to_dict(),
            {
                "error_code": "timeout",
                "retryable": True,
                "error_message": "retry later",
            },
        )


if __name__ == "__main__":
    unittest.main()

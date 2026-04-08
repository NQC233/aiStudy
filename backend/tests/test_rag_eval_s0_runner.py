from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.rag_eval_s0_runner import QuestionItem, validate_dataset_contract


class ValidateDatasetContractTestCase(unittest.TestCase):
    def test_validate_dataset_contract_accepts_balanced_dataset(self) -> None:
        questions: list[QuestionItem] = []
        for asset_id in ("asset-a", "asset-b", "asset-c"):
            for index in range(10):
                questions.append(
                    QuestionItem(
                        question_id=f"{asset_id}-zh-{index}",
                        asset_id=asset_id,
                        question_lang="zh",
                        question="q",
                        expected_block_id="blk-1",
                        expected_page=1,
                        expected_paragraph=1,
                        answer_keypoints=[],
                    )
                )
                questions.append(
                    QuestionItem(
                        question_id=f"{asset_id}-en-{index}",
                        asset_id=asset_id,
                        question_lang="en",
                        question="q",
                        expected_block_id="blk-1",
                        expected_page=1,
                        expected_paragraph=1,
                        answer_keypoints=[],
                    )
                )

        validate_dataset_contract(
            questions,
            expected_total=60,
            expected_asset_count=3,
            expected_per_asset=20,
            expected_per_language_per_asset=10,
        )

    def test_validate_dataset_contract_rejects_language_imbalance(self) -> None:
        questions: list[QuestionItem] = []
        for index in range(20):
            questions.append(
                QuestionItem(
                    question_id=f"asset-a-en-{index}",
                    asset_id="asset-a",
                    question_lang="en",
                    question="q",
                    expected_block_id="blk-1",
                    expected_page=1,
                    expected_paragraph=1,
                    answer_keypoints=[],
                )
            )
        for asset_id in ("asset-b", "asset-c"):
            for index in range(10):
                questions.append(
                    QuestionItem(
                        question_id=f"{asset_id}-zh-{index}",
                        asset_id=asset_id,
                        question_lang="zh",
                        question="q",
                        expected_block_id="blk-1",
                        expected_page=1,
                        expected_paragraph=1,
                        answer_keypoints=[],
                    )
                )
                questions.append(
                    QuestionItem(
                        question_id=f"{asset_id}-en-{index}",
                        asset_id=asset_id,
                        question_lang="en",
                        question="q",
                        expected_block_id="blk-1",
                        expected_page=1,
                        expected_paragraph=1,
                        answer_keypoints=[],
                    )
                )

        with self.assertRaisesRegex(ValueError, "language balance"):
            validate_dataset_contract(
                questions,
                expected_total=60,
                expected_asset_count=3,
                expected_per_asset=20,
                expected_per_language_per_asset=10,
            )


if __name__ == "__main__":
    unittest.main()

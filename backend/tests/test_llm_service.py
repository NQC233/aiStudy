import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.llm_service import _extract_json_object


class LlmServiceTests(unittest.TestCase):
    def test_extract_json_object_tolerates_invalid_backslash_sequences(self) -> None:
        raw = (
            "{"
            '"title":"关键机制解析",'
            '"goal":"讲解关键机制",'
            '"script":"公式 $s_B(x)=\\mathsf{Linear}_N(x)$。",'
            '"evidence":"证据[1]"'
            "}"
        )

        payload = _extract_json_object(raw)

        self.assertEqual(payload["title"], "关键机制解析")
        self.assertIn("\\mathsf", payload["script"])


if __name__ == "__main__":
    unittest.main()

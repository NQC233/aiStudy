import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.reader import ParsedDocumentPayload
from app.services.mindmap_service import _build_generated_nodes


class MindmapStoryGraphTests(unittest.TestCase):
    def test_builds_story_nodes_and_evidence_nodes(self) -> None:
        payload = ParsedDocumentPayload.model_validate(
            {
                "schema_version": "v1",
                "asset_id": "asset-1",
                "parse_id": "parse-1",
                "document": {"title": "A Great Paper"},
                "pages": [
                    {
                        "page_id": "p1",
                        "page_no": 1,
                        "source_page_idx": 0,
                        "blocks": ["b1", "b2"],
                    },
                    {
                        "page_id": "p2",
                        "page_no": 2,
                        "source_page_idx": 1,
                        "blocks": ["b3", "b4"],
                    },
                ],
                "sections": [
                    {
                        "section_id": "s1",
                        "title": "Introduction",
                        "level": 1,
                        "page_start": 1,
                        "page_end": 1,
                        "block_ids": ["b1"],
                    },
                    {
                        "section_id": "s2",
                        "title": "Method",
                        "level": 1,
                        "page_start": 1,
                        "page_end": 2,
                        "block_ids": ["b2", "b3"],
                    },
                    {
                        "section_id": "s3",
                        "title": "Experiments",
                        "level": 1,
                        "page_start": 2,
                        "page_end": 2,
                        "block_ids": ["b4"],
                    },
                ],
                "blocks": [
                    {
                        "block_id": "b1",
                        "type": "paragraph",
                        "page_no": 1,
                        "source_page_idx": 0,
                        "order": 1,
                        "section_id": "s1",
                        "text": "We address the problem of paper understanding.",
                    },
                    {
                        "block_id": "b2",
                        "type": "paragraph",
                        "page_no": 1,
                        "source_page_idx": 0,
                        "order": 2,
                        "section_id": "s2",
                        "text": "Our method uses staged retrieval and explanation.",
                    },
                    {
                        "block_id": "b3",
                        "type": "paragraph",
                        "page_no": 2,
                        "source_page_idx": 1,
                        "order": 3,
                        "section_id": "s2",
                        "text": "Mechanism details include cross-page evidence linking.",
                    },
                    {
                        "block_id": "b4",
                        "type": "paragraph",
                        "page_no": 2,
                        "source_page_idx": 1,
                        "order": 4,
                        "section_id": "s3",
                        "text": "Experiment shows strong gains and clear conclusion.",
                    },
                ],
            }
        )

        nodes = _build_generated_nodes(payload)
        node_keys = {node.node_key for node in nodes}

        self.assertIn("story:problem", node_keys)
        self.assertIn("story:method", node_keys)
        self.assertIn("story:experiment", node_keys)

        evidence_nodes = [node for node in nodes if node.node_key.startswith("ev:")]
        self.assertGreaterEqual(len(evidence_nodes), 2)
        self.assertTrue(
            all(
                node.parent_key and node.parent_key.startswith("story:")
                for node in evidence_nodes
            )
        )


if __name__ == "__main__":
    unittest.main()

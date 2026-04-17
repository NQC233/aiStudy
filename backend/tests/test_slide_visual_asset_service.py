import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.slide_visual_asset_service import build_visual_asset_cards
from app.services.slide_visual_asset_service import extract_asset_surrounding_context


class SlideVisualAssetServiceTestCase(unittest.TestCase):
    def test_extract_asset_surrounding_context_uses_neighbor_blocks(self) -> None:
        blocks = [
            {
                "block_id": "blk-0001",
                "type": "paragraph",
                "text": "The model uses stacked self-attention layers.",
            },
            {
                "block_id": "blk-0002",
                "type": "image",
                "text": None,
            },
            {
                "block_id": "blk-0003",
                "type": "paragraph",
                "text": "The decoder attends to encoder outputs through cross-attention.",
            },
        ]

        context = extract_asset_surrounding_context(blocks, block_id="blk-0002")

        self.assertIn("stacked self-attention layers", context)
        self.assertIn("cross-attention", context)

    def test_build_visual_asset_cards_uses_caption_and_context(self) -> None:
        assets = [
            {
                "resource_id": "fig-1",
                "type": "image",
                "page_no": 4,
                "block_id": "block-fig-1",
                "caption": ["Figure 1: Transformer architecture."],
                "surrounding_context": "The encoder and decoder are both composed of stacked self-attention layers.",
                "public_url": "https://example.com/fig1.png",
            }
        ]

        cards = build_visual_asset_cards(
            assets,
            describe_asset=lambda asset: {
                "vision_summary": asset["caption_text"],
                "recommended_usage": "method_overview",
            },
        )

        self.assertEqual(cards[0]["asset_id"], "fig-1")
        self.assertEqual(cards[0]["recommended_usage"], "method_overview")
        self.assertEqual(cards[0]["caption_text"], "Figure 1: Transformer architecture.")

    def test_build_visual_asset_cards_preserves_page_and_block_anchor(self) -> None:
        assets = [
            {
                "resource_id": "tbl-2",
                "type": "table",
                "page_no": 9,
                "block_id": "block-table-2",
                "caption": ["Table 2: BLEU comparison."],
                "surrounding_context": "We compare against strong recurrent and convolutional baselines.",
                "public_url": "https://example.com/table2.png",
            }
        ]

        cards = build_visual_asset_cards(
            assets,
            describe_asset=lambda _asset: {
                "vision_summary": "BLEU result table",
                "recommended_usage": "results_comparison",
            },
        )

        self.assertEqual(cards[0]["page_no"], 9)
        self.assertEqual(cards[0]["block_id"], "block-table-2")

    def test_build_visual_asset_cards_exposes_normalized_asset_id_to_describer(self) -> None:
        assets = [
            {
                "resource_id": "img-9",
                "type": "image",
                "page_no": 2,
                "block_id": "block-9",
                "caption": ["Figure 9: Attention heads."],
                "surrounding_context": "Different heads attend to different token relations.",
                "public_url": "https://example.com/fig9.png",
            }
        ]

        seen_asset_ids: list[str] = []

        build_visual_asset_cards(
            assets,
            describe_asset=lambda asset: {
                "vision_summary": seen_asset_ids.append(str(asset["asset_id"])) or "ok",
                "recommended_usage": "attention_visualization",
            },
        )

        self.assertEqual(seen_asset_ids, ["img-9"])


if __name__ == "__main__":
    unittest.main()

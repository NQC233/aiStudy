import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.reader import ParsedDocumentBlock, ParsedDocumentPayload, ParsedDocumentSection
from app.services.chunk_builder_service import build_chunks_from_parsed_payload


def _payload_with_blocks(blocks: list[ParsedDocumentBlock], sections: list[ParsedDocumentSection]) -> ParsedDocumentPayload:
    return ParsedDocumentPayload(
        schema_version="1",
        asset_id="asset-1",
        parse_id="parse-1",
        sections=sections,
        blocks=blocks,
        reading_order=[block.block_id for block in blocks],
    )


class ChunkBuilderServiceTests(unittest.TestCase):
    def test_build_chunks_filters_front_matter_reference_and_permission_noise(self) -> None:
        sections = [
            ParsedDocumentSection(section_id="front", title="Attention Is All You Need", level=1, parent_id=None, page_start=1, page_end=1),
            ParsedDocumentSection(section_id="intro", title="Introduction", level=1, parent_id=None, page_start=2, page_end=2),
            ParsedDocumentSection(section_id="refs", title="References", level=1, parent_id=None, page_start=10, page_end=10),
        ]
        blocks = [
            ParsedDocumentBlock(
                block_id="blk-authors",
                type="paragraph",
                page_no=1,
                source_page_idx=0,
                order=1,
                section_id="front",
                text="Attention Is All You Need\nAshish Vaswani Google Brain\nNoam Shazeer Google Brain",
            ),
            ParsedDocumentBlock(
                block_id="blk-permission",
                type="paragraph",
                page_no=1,
                source_page_idx=0,
                order=2,
                section_id="front",
                text="Provided proper attribution is provided, Google hereby grants permission to reproduce the tables and figures in this paper.",
            ),
            ParsedDocumentBlock(
                block_id="blk-good",
                type="paragraph",
                page_no=2,
                source_page_idx=1,
                order=3,
                section_id="intro",
                text="Recurrent models preclude parallelization within training examples, which becomes critical at longer sequence lengths.",
            ),
            ParsedDocumentBlock(
                block_id="blk-ref",
                type="paragraph",
                page_no=10,
                source_page_idx=9,
                order=4,
                section_id="refs",
                text="[1] Bahdanau et al. Neural machine translation by jointly learning to align and translate.",
            ),
        ]

        chunks = build_chunks_from_parsed_payload(_payload_with_blocks(blocks, sections))

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].block_ids, ["blk-good"])

    def test_build_chunks_filters_page_one_title_section_author_paragraphs(self) -> None:
        sections = [
            ParsedDocumentSection(
                section_id="front",
                title="Attention Is All You Need",
                level=1,
                parent_id=None,
                page_start=1,
                page_end=1,
            ),
            ParsedDocumentSection(
                section_id="abstract",
                title="Abstract",
                level=1,
                parent_id=None,
                page_start=1,
                page_end=1,
            ),
        ]
        blocks = [
            ParsedDocumentBlock(
                block_id="blk-author-1",
                type="paragraph",
                page_no=1,
                source_page_idx=0,
                order=1,
                section_id="front",
                text="Ashish Vaswani Google Brain avaswani@google.com",
            ),
            ParsedDocumentBlock(
                block_id="blk-author-2",
                type="paragraph",
                page_no=1,
                source_page_idx=0,
                order=2,
                section_id="front",
                text="Noam Shazeer Google Brain noam@google.com",
            ),
            ParsedDocumentBlock(
                block_id="blk-abstract",
                type="paragraph",
                page_no=1,
                source_page_idx=0,
                order=3,
                section_id="abstract",
                text="The Transformer is based solely on attention mechanisms and improves translation quality.",
            ),
        ]

        chunks = build_chunks_from_parsed_payload(_payload_with_blocks(blocks, sections))

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].block_ids, ["blk-abstract"])

    def test_build_chunks_skips_heading_only_noise_but_keeps_heading_context_with_body(self) -> None:
        sections = [
            ParsedDocumentSection(section_id="results", title="Results", level=1, parent_id=None, page_start=8, page_end=8),
        ]
        blocks = [
            ParsedDocumentBlock(
                block_id="blk-heading-only",
                type="heading",
                page_no=8,
                source_page_idx=7,
                order=1,
                section_id="results",
                text="6 Results",
            ),
            ParsedDocumentBlock(
                block_id="blk-results-body",
                type="paragraph",
                page_no=8,
                source_page_idx=7,
                order=2,
                section_id="results",
                text="Table 2 summarizes our results and compares translation quality and training costs to prior architectures.",
            ),
        ]

        chunks = build_chunks_from_parsed_payload(_payload_with_blocks(blocks, sections))

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].block_ids, ["blk-results-body"])
        self.assertNotIn("6 Results", chunks[0].text_content)

    def test_build_chunks_filters_broken_ocr_noise(self) -> None:
        sections = [
            ParsedDocumentSection(section_id="appendix", title="Appendix", level=1, parent_id=None, page_start=13, page_end=13),
            ParsedDocumentSection(section_id="method", title="Model Architecture", level=1, parent_id=None, page_start=3, page_end=3),
        ]
        blocks = [
            ParsedDocumentBlock(
                block_id="blk-noise",
                type="paragraph",
                page_no=13,
                source_page_idx=12,
                order=1,
                section_id="appendix",
                text="Attention VisualizationsInput-Input Laye",
            ),
            ParsedDocumentBlock(
                block_id="blk-method",
                type="paragraph",
                page_no=3,
                source_page_idx=2,
                order=2,
                section_id="method",
                text="The Transformer follows an encoder-decoder architecture using stacked self-attention layers.",
            ),
        ]

        chunks = build_chunks_from_parsed_payload(_payload_with_blocks(blocks, sections))

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].block_ids, ["blk-method"])

    def test_build_chunks_adds_image_asset_candidate_from_caption_and_context(self) -> None:
        sections = [
            ParsedDocumentSection(
                section_id="method",
                title="Model Architecture",
                level=1,
                parent_id=None,
                page_start=3,
                page_end=3,
            ),
        ]
        blocks = [
            ParsedDocumentBlock(
                block_id="blk-arch",
                type="paragraph",
                page_no=3,
                source_page_idx=2,
                order=1,
                section_id="method",
                text="The Transformer follows an encoder-decoder architecture shown in Figure 1.",
            )
        ]
        payload = _payload_with_blocks(blocks, sections)
        payload.assets.images = [
            {
                "resource_id": "fig-1",
                "type": "image",
                "page_no": 3,
                "block_id": "blk-arch",
                "caption": ["Figure 1. The Transformer architecture."],
                "public_url": "https://example.com/fig-1.png",
            }
        ]

        chunks = build_chunks_from_parsed_payload(payload)

        asset_chunks = [chunk for chunk in chunks if "asset:fig-1" in chunk.block_ids]
        self.assertEqual(len(asset_chunks), 1)
        self.assertIn("Figure 1. The Transformer architecture.", asset_chunks[0].text_content)
        self.assertIn("encoder-decoder architecture", asset_chunks[0].text_content)

    def test_build_chunks_adds_table_asset_candidate_from_caption_and_context(self) -> None:
        sections = [
            ParsedDocumentSection(
                section_id="results",
                title="Machine Translation",
                level=1,
                parent_id=None,
                page_start=8,
                page_end=8,
            ),
        ]
        blocks = [
            ParsedDocumentBlock(
                block_id="blk-results",
                type="paragraph",
                page_no=8,
                source_page_idx=7,
                order=1,
                section_id="results",
                text="Table 2 summarizes our translation quality and training cost comparisons.",
            )
        ]
        payload = _payload_with_blocks(blocks, sections)
        payload.assets.tables = [
            {
                "resource_id": "tbl-2",
                "type": "table",
                "page_no": 8,
                "block_id": "blk-results",
                "caption": ["Table 2. Transformer BLEU and training cost comparison."],
                "public_url": "https://example.com/table-2.png",
            }
        ]

        chunks = build_chunks_from_parsed_payload(payload)

        asset_chunks = [chunk for chunk in chunks if "asset:tbl-2" in chunk.block_ids]
        self.assertEqual(len(asset_chunks), 1)
        self.assertIn("Table 2. Transformer BLEU and training cost comparison.", asset_chunks[0].text_content)
        self.assertIn("translation quality and training cost", asset_chunks[0].text_content)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from collections.abc import Callable


def extract_asset_surrounding_context(
    blocks: list[dict[str, object]], *, block_id: str, radius: int = 1
) -> str:
    target_index = next(
        (index for index, block in enumerate(blocks) if block.get("block_id") == block_id),
        None,
    )
    if target_index is None:
        return ""

    texts: list[str] = []
    start = max(0, target_index - radius)
    end = min(len(blocks), target_index + radius + 1)
    for index in range(start, end):
        if index == target_index:
            continue
        text = blocks[index].get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    return " ".join(texts)


def _join_text_list(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return "\n".join(parts)
    return ""


def build_visual_asset_cards(
    assets: list[dict[str, object]],
    *,
    describe_asset: Callable[[dict[str, object]], dict[str, str]],
) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    for asset in assets:
        asset_id = str(asset.get("resource_id", ""))
        asset_type = str(asset.get("type", ""))
        caption_text = _join_text_list(asset.get("caption"))
        asset_for_description = {
            **asset,
            "asset_id": asset_id,
            "asset_type": asset_type,
            "caption_text": caption_text,
        }
        described = describe_asset(asset_for_description)
        cards.append(
            {
                "asset_id": asset_id,
                "asset_type": asset_type,
                "page_no": asset.get("page_no"),
                "block_id": asset.get("block_id", ""),
                "caption": asset.get("caption", []),
                "caption_text": caption_text,
                "surrounding_context": asset.get("surrounding_context", ""),
                "public_url": asset.get("public_url", asset.get("path", "")),
                "vision_summary": described.get("vision_summary", ""),
                "recommended_usage": described.get(
                    "recommended_usage", "general_visual"
                ),
            }
        )
    return cards

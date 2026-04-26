from __future__ import annotations

from typing import Any

import dashscope
from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.presentation import Presentation
from app.schemas.slide_dsl import (
    AssetSlideTtsEnsureResponse,
    AssetSlideTtsRetryNextResponse,
    SlidesDslPayload,
    SlideTtsManifest,
)
from app.services.asset_service import require_user_asset
from app.services.oss_service import build_slide_tts_audio_key, upload_bytes
from app.services.slide_playback_service import (
    build_tts_manifest_placeholders,
    resolve_tts_status,
)


class SlideTtsConfigurationError(RuntimeError):
    """TTS 配置缺失或非法。"""


class SlideTtsRequestError(RuntimeError):
    """TTS 请求失败。"""


def choose_tts_target_slide_keys(
    slide_keys: list[str],
    page_index: int,
    prefetch_next: bool,
) -> list[str]:
    if page_index < 0 or page_index >= len(slide_keys):
        raise ValueError("page_index 超出范围")
    targets = [slide_keys[page_index]]
    if prefetch_next and page_index + 1 < len(slide_keys):
        targets.append(slide_keys[page_index + 1])
    return targets


def enqueue_manifest_targets(
    manifest: SlideTtsManifest, targets: list[str]
) -> list[str]:
    enqueued: list[str] = []
    target_set = set(targets)
    for item in manifest.pages:
        if item.slide_key not in target_set:
            continue
        if item.status in {"pending", "failed"}:
            item.status = "processing"
            item.error_message = None
            item.retry_meta = None
            enqueued.append(item.slide_key)
    return enqueued


def _ensure_tts_configuration() -> tuple[str, str, str]:
    if not settings.dashscope_api_key:
        raise SlideTtsConfigurationError("未配置 DASHSCOPE_API_KEY，无法调用 TTS。")

    model_name = settings.dashscope_tts_model_name.strip()
    if not model_name:
        raise SlideTtsConfigurationError("DASHSCOPE_TTS_MODEL_NAME 不能为空。")

    voice = settings.dashscope_tts_voice.strip()
    if not voice:
        raise SlideTtsConfigurationError("DASHSCOPE_TTS_VOICE 不能为空。")

    return settings.dashscope_api_key, model_name, voice


def resolve_tts_voice_for_model(model_name: str, requested_voice: str) -> str:
    model = model_name.strip().lower()
    voice = requested_voice.strip()
    if model.startswith("cosyvoice-v3") and voice == "longxiaochun":
        return "longxiaochun_v3"
    return voice


def synthesize_slide_tts_audio(text: str) -> bytes:
    api_key, model_name, voice = _ensure_tts_configuration()
    script = text.strip()
    if not script:
        raise SlideTtsRequestError("当前页面缺少讲稿文本，无法生成 TTS。")

    resolved_voice = resolve_tts_voice_for_model(model_name, voice)
    dashscope.api_key = api_key
    try:
        synthesizer = SpeechSynthesizer(
            model=model_name,
            voice=resolved_voice,
            format=AudioFormat.MP3_22050HZ_MONO_256KBPS,
        )
        audio_data = synthesizer.call(
            script,
            timeout_millis=max(settings.dashscope_tts_timeout_sec, 1) * 1000,
        )
    except Exception as exc:
        raise SlideTtsRequestError(f"TTS 请求失败：{str(exc)[:320]}") from exc

    if not isinstance(audio_data, (bytes, bytearray)) or len(audio_data) == 0:
        raise SlideTtsRequestError("TTS 返回为空，可能是音色与模型不匹配。")
    return bytes(audio_data)


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return asset


def _load_presentation_with_slides(db: Session, asset_id: str) -> Presentation:
    presentation = db.scalars(
        select(Presentation).where(Presentation.asset_id == asset_id).with_for_update()
    ).first()
    if presentation is None or not presentation.slides_dsl:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前资产尚未生成 slides DSL，无法触发 TTS。",
        )
    return presentation


def _manifest_for_presentation(presentation: Presentation) -> SlideTtsManifest:
    slides_dsl = SlidesDslPayload.model_validate(presentation.slides_dsl)
    if isinstance(presentation.tts_manifest, dict) and presentation.tts_manifest:
        return SlideTtsManifest.model_validate(presentation.tts_manifest)
    return build_tts_manifest_placeholders(slides_dsl)


def ensure_asset_slide_tts(
    db: Session,
    asset_id: str,
    user_id: str,
    page_index: int,
    prefetch_next: bool = True,
) -> AssetSlideTtsEnsureResponse:
    require_user_asset(db, asset_id, user_id)
    presentation = _load_presentation_with_slides(db, asset_id)
    slides_dsl = SlidesDslPayload.model_validate(presentation.slides_dsl)
    manifest = _manifest_for_presentation(presentation)

    slide_keys = [item.slide_key for item in slides_dsl.pages]
    try:
        targets = choose_tts_target_slide_keys(
            slide_keys,
            page_index=page_index,
            prefetch_next=prefetch_next,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    enqueued = enqueue_manifest_targets(manifest, targets)

    presentation.tts_manifest = manifest.model_dump(mode="json")
    db.commit()

    tts_status = resolve_tts_status([item.status for item in manifest.pages])
    message = "已加入 TTS 生成队列。" if enqueued else "目标页面已在处理中或已就绪。"
    return AssetSlideTtsEnsureResponse(
        asset_id=asset_id,
        page_index=page_index,
        enqueued_slide_keys=enqueued,
        tts_status=tts_status,
        message=message,
    )


def retry_next_asset_slide_tts(
    db: Session,
    asset_id: str,
    user_id: str,
    current_page_index: int,
) -> AssetSlideTtsRetryNextResponse:
    require_user_asset(db, asset_id, user_id)
    presentation = _load_presentation_with_slides(db, asset_id)
    slides_dsl = SlidesDslPayload.model_validate(presentation.slides_dsl)
    manifest = _manifest_for_presentation(presentation)

    next_page_index = current_page_index + 1
    if next_page_index < 0 or next_page_index >= len(slides_dsl.pages):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前已是最后一页，无法重试下一页。",
        )

    next_slide_key = slides_dsl.pages[next_page_index].slide_key
    for item in manifest.pages:
        if item.slide_key == next_slide_key and item.status == "failed":
            item.status = "pending"
            item.error_message = None
            item.retry_meta = None

    enqueued = enqueue_manifest_targets(manifest, [next_slide_key])
    presentation.tts_manifest = manifest.model_dump(mode="json")
    db.commit()

    tts_status = resolve_tts_status([item.status for item in manifest.pages])
    message = "下一页已重新加入 TTS 生成队列。" if enqueued else "下一页当前不可重试。"
    return AssetSlideTtsRetryNextResponse(
        asset_id=asset_id,
        current_page_index=current_page_index,
        next_slide_key=next_slide_key,
        enqueued_slide_keys=enqueued,
        tts_status=tts_status,
        message=message,
    )


def run_asset_slide_tts_pipeline(
    db: Session, asset_id: str, slide_key: str
) -> dict[str, Any]:
    asset = _require_asset(db, asset_id)
    presentation = _load_presentation_with_slides(db, asset_id)
    slides_dsl = SlidesDslPayload.model_validate(presentation.slides_dsl)
    manifest = _manifest_for_presentation(presentation)

    page_by_key = {page.slide_key: page for page in slides_dsl.pages}
    page = page_by_key.get(slide_key)
    if page is None:
        raise RuntimeError("TTS 目标页面不存在。")

    manifest_item = next(
        (item for item in manifest.pages if item.slide_key == slide_key), None
    )
    if manifest_item is None:
        raise RuntimeError("TTS manifest 与 slides_dsl 不一致。")

    if manifest_item.status == "ready" and manifest_item.audio_url:
        return {"asset_id": asset_id, "slide_key": slide_key, "status": "ready"}

    if manifest_item.status != "processing":
        manifest_item.status = "processing"
        manifest_item.error_message = None
        manifest_item.retry_meta = None
        presentation.tts_manifest = manifest.model_dump(mode="json")
        db.commit()

    script_text = ""
    for block in page.blocks:
        if block.block_type == "script":
            script_text = block.content
            break

    try:
        audio_bytes = synthesize_slide_tts_audio(script_text)
        storage_key = build_slide_tts_audio_key(
            user_id=asset.user_id,
            asset_id=asset.id,
            presentation_version=presentation.version,
            slide_key=slide_key,
        )
        upload_result = upload_bytes(
            storage_key=storage_key,
            content=audio_bytes,
            content_type="audio/mpeg",
        )

        presentation = _load_presentation_with_slides(db, asset_id)
        manifest = _manifest_for_presentation(presentation)
        manifest_item = next(
            (item for item in manifest.pages if item.slide_key == slide_key),
            None,
        )
        if manifest_item is None:
            raise RuntimeError("TTS manifest 在回写阶段缺少目标页面。")
        manifest_item.status = "ready"
        manifest_item.audio_url = upload_result.public_url
        manifest_item.duration_ms = manifest_item.duration_ms or 3000
        manifest_item.error_message = None
        manifest_item.retry_meta = None
        presentation.tts_manifest = manifest.model_dump(mode="json")
        db.commit()
        return {
            "asset_id": asset_id,
            "slide_key": slide_key,
            "status": "ready",
            "audio_url": upload_result.public_url,
        }
    except Exception as exc:
        presentation = _load_presentation_with_slides(db, asset_id)
        manifest = _manifest_for_presentation(presentation)
        manifest_item = next(
            (item for item in manifest.pages if item.slide_key == slide_key),
            None,
        )
        if manifest_item is not None:
            manifest_item.status = "failed"
            manifest_item.error_message = str(exc)[:500]
            manifest_item.retry_meta = None
            presentation.tts_manifest = manifest.model_dump(mode="json")
            db.commit()
        raise

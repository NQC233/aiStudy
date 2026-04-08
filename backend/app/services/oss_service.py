from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import oss2

from app.core.config import settings


class OSSConfigurationError(RuntimeError):
    """OSS 配置缺失时抛出的异常。"""


class OSSUploadResult:
    """封装 OSS 上传结果，便于上层服务复用。"""

    def __init__(self, storage_key: str, public_url: str) -> None:
        self.storage_key = storage_key
        self.public_url = public_url


def _build_asset_prefix(user_id: str, asset_id: str) -> str:
    prefix = settings.aliyun_oss_base_prefix.strip("/")
    return f"{prefix}/users/{user_id}/assets/{asset_id}"


def _create_bucket() -> oss2.Bucket:
    if not settings.aliyun_oss_endpoint:
        raise OSSConfigurationError("未配置阿里云 OSS endpoint。")
    if not settings.aliyun_oss_bucket:
        raise OSSConfigurationError("未配置阿里云 OSS bucket。")
    if (
        not settings.aliyun_oss_access_key_id
        or not settings.aliyun_oss_access_key_secret
    ):
        raise OSSConfigurationError("未配置阿里云 OSS 访问密钥。")

    auth = oss2.Auth(
        settings.aliyun_oss_access_key_id, settings.aliyun_oss_access_key_secret
    )
    return oss2.Bucket(
        auth, f"https://{settings.aliyun_oss_endpoint}", settings.aliyun_oss_bucket
    )


def build_asset_pdf_key(user_id: str, asset_id: str, filename: str) -> str:
    """生成原始 PDF 在 OSS 中的对象路径。"""
    suffix = Path(filename).suffix.lower() or ".pdf"
    safe_name = Path(filename).stem.strip().replace(" ", "-") or "paper"
    object_name = f"{safe_name}{suffix}"
    return f"{_build_asset_prefix(user_id=user_id, asset_id=asset_id)}/original/{object_name}"


def build_parse_artifact_key(
    user_id: str, asset_id: str, parse_id: str, relative_path: str
) -> str:
    """生成解析产物在 OSS 中的对象路径。"""
    normalized_path = relative_path.strip("/").replace("\\", "/")
    return f"{_build_asset_prefix(user_id=user_id, asset_id=asset_id)}/parses/{parse_id}/{normalized_path}"


def build_slide_tts_audio_key(
    user_id: str,
    asset_id: str,
    presentation_version: int,
    slide_key: str,
) -> str:
    safe_slide_key = (
        slide_key.strip().replace(":", "-").replace("/", "-").replace(" ", "-")
    )
    return (
        f"{_build_asset_prefix(user_id=user_id, asset_id=asset_id)}"
        f"/slides/v{presentation_version}/tts/{safe_slide_key}.mp3"
    )


def build_public_url(storage_key: str) -> str:
    """生成 MinerU 后续可访问的 URL。"""
    key = quote(storage_key)

    if not settings.aliyun_oss_bucket or not settings.aliyun_oss_endpoint:
        raise OSSConfigurationError("OSS bucket 或 endpoint 缺失，无法生成公开地址。")

    if settings.aliyun_oss_mineru_use_origin_url:
        return (
            f"https://{settings.aliyun_oss_bucket}.{settings.aliyun_oss_endpoint}/{key}"
        )

    if settings.aliyun_oss_public_base_url:
        return f"{settings.aliyun_oss_public_base_url.rstrip('/')}/{key}"

    return f"https://{settings.aliyun_oss_bucket}.{settings.aliyun_oss_endpoint}/{key}"


def upload_pdf_bytes(
    user_id: str, asset_id: str, filename: str, content: bytes, content_type: str
) -> OSSUploadResult:
    """将上传的 PDF 内容写入 OSS，并返回对象路径和外部访问地址。"""
    storage_key = build_asset_pdf_key(
        user_id=user_id, asset_id=asset_id, filename=filename
    )
    return upload_bytes(
        storage_key=storage_key, content=content, content_type=content_type
    )


def upload_bytes(
    storage_key: str, content: bytes, content_type: str
) -> OSSUploadResult:
    """将任意字节内容写入 OSS，并返回对象路径和外部访问地址。"""
    bucket = _create_bucket()
    headers = {"Content-Type": content_type}
    bucket.put_object(storage_key, content, headers=headers)
    return OSSUploadResult(
        storage_key=storage_key, public_url=build_public_url(storage_key)
    )


def delete_objects(storage_keys: list[str]) -> tuple[int, list[str]]:
    """删除给定 OSS 对象，返回成功数量与失败 key。"""
    if not storage_keys:
        return 0, []

    bucket = _create_bucket()
    deleted_count = 0
    failed_keys: list[str] = []
    for key in storage_keys:
        normalized = (key or "").strip().lstrip("/")
        if not normalized:
            continue
        try:
            bucket.delete_object(normalized)
            deleted_count += 1
        except Exception:
            failed_keys.append(normalized)
    return deleted_count, failed_keys


def delete_asset_prefix_objects(user_id: str, asset_id: str) -> tuple[int, list[str]]:
    """按资产前缀清理 OSS 对象，避免漏删未入库 key。"""
    bucket = _create_bucket()
    prefix = f"{_build_asset_prefix(user_id=user_id, asset_id=asset_id)}/"
    deleted_count = 0
    failed_keys: list[str] = []
    for obj in oss2.ObjectIteratorV2(bucket, prefix=prefix):
        try:
            bucket.delete_object(obj.key)
            deleted_count += 1
        except Exception:
            failed_keys.append(obj.key)
    return deleted_count, failed_keys

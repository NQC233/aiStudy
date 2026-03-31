from datetime import datetime

from pydantic import BaseModel, Field


class ParseProgress(BaseModel):
    extracted_pages: int | None = None
    total_pages: int | None = None
    start_time: str | None = None


class ParseTaskSnapshot(BaseModel):
    task_id: str | None = None
    data_id: str | None = None
    state: str | None = None
    trace_id: str | None = None
    full_zip_url: str | None = None
    err_msg: str | None = None
    progress: ParseProgress | None = None


class DocumentParseSummary(BaseModel):
    id: str
    asset_id: str
    provider: str
    parse_version: str
    status: str
    markdown_storage_key: str | None = None
    json_storage_key: str | None = None
    raw_response_storage_key: str | None = None
    task: ParseTaskSnapshot = Field(default_factory=ParseTaskSnapshot)
    error_code: str | None = None
    retryable: bool | None = None
    attempt: int | None = None
    max_retries: int | None = None
    next_retry_eta: str | None = None
    created_at: datetime
    updated_at: datetime


class AssetParseStatusResponse(BaseModel):
    asset_id: str
    asset_status: str
    parse_status: str
    error_message: str | None = None
    latest_parse: DocumentParseSummary | None = None


class AssetParseRetryResponse(BaseModel):
    asset_id: str
    parse_status: str
    message: str

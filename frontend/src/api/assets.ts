export interface AssetListItem {
  id: string;
  title: string;
  authors: string[];
  source_type: string;
  status: string;
  created_at: string;
}

export interface AssetDetail {
  id: string;
  user_id: string;
  title: string;
  authors: string[];
  abstract: string | null;
  source_type: string;
  language: string;
  status: string;
  parse_error_message: string | null;
  created_at: string;
  updated_at: string;
  basic_resources: {
    parse_status: string;
    kb_status: string;
    mindmap_status: string;
  };
  enhanced_resources: {
    slides_status: string;
    anki_status: string;
    quiz_status: string;
  };
}

export interface AssetPdfDescriptor {
  asset_id: string;
  file_id: string;
  file_type: string;
  mime_type: string;
  size: number;
  url: string;
}

export interface AssetUploadResponse {
  asset: AssetDetail;
  uploaded_file_id: string;
  uploaded_file_url: string;
}

export interface AssetParseStatusResponse {
  asset_id: string;
  asset_status: string;
  parse_status: string;
  error_message: string | null;
  latest_parse: {
    id: string;
    asset_id: string;
    provider: string;
    parse_version: string;
    status: string;
    markdown_storage_key: string | null;
    json_storage_key: string | null;
    raw_response_storage_key: string | null;
    task: {
      task_id: string | null;
      data_id: string | null;
      state: string | null;
      trace_id: string | null;
      full_zip_url: string | null;
      err_msg: string | null;
      progress: {
        extracted_pages: number | null;
        total_pages: number | null;
        start_time: string | null;
      } | null;
    };
    created_at: string;
    updated_at: string;
  } | null;
}

export interface AssetParseRetryResponse {
  asset_id: string;
  parse_status: string;
  message: string;
}

export interface ParsedDocumentPage {
  page_id: string;
  page_no: number;
  source_page_idx: number;
  width: number | null;
  height: number | null;
  blocks: string[];
}

export interface ParsedDocumentSection {
  section_id: string;
  title: string;
  level: number;
  parent_id: string | null;
  page_start: number;
  page_end: number;
  block_ids: string[];
}

export interface ParsedDocumentBlock {
  block_id: string;
  type: string;
  page_no: number;
  source_page_idx: number;
  order: number;
  section_id: string;
  bbox: number[] | null;
  text: string | null;
  text_level: number | null;
  paragraph_no: number | null;
  anchor: Record<string, unknown>;
  source_refs: Record<string, unknown>;
  resource_ref: string | null;
  metadata: Record<string, unknown>;
}

export interface ParsedDocumentTocItem {
  section_id: string;
  title: string;
  level: number;
  page_start: number;
}

export interface ParsedDocumentPayload {
  schema_version: string;
  asset_id: string;
  parse_id: string;
  provider: Record<string, unknown>;
  document: Record<string, unknown>;
  pages: ParsedDocumentPage[];
  sections: ParsedDocumentSection[];
  blocks: ParsedDocumentBlock[];
  assets: {
    images: Record<string, unknown>[];
    tables: Record<string, unknown>[];
  };
  reading_order: string[];
  toc: ParsedDocumentTocItem[];
  stats: Record<string, unknown>;
}

export interface AssetParsedDocumentResponse {
  asset_id: string;
  parse_status: string;
  parse_id: string | null;
  parsed_json: ParsedDocumentPayload | null;
}

export interface AnchorPreviewRequest {
  page_no: number;
  selected_text: string;
  block_id?: string | null;
  paragraph_no?: number | null;
  selector_type?: string;
  selector_payload?: Record<string, unknown>;
}

export interface AnchorPreviewResponse {
  asset_id: string;
  page_no: number;
  block_id: string;
  paragraph_no: number | null;
  selected_text: string;
  selector_type: string;
  selector_payload: Record<string, unknown>;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const DEFAULT_REQUEST_TIMEOUT_MS = 10000;
const UPLOAD_REQUEST_TIMEOUT_MS = 180000;

async function requestWithTimeout(input: RequestInfo | URL, init?: RequestInit, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('请求超时，请检查后端服务或资源地址。');
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

async function requestJson<T>(path: string): Promise<T> {
  const response = await requestWithTimeout(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}


async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await requestWithTimeout(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}


export function fetchAssets(): Promise<AssetListItem[]> {
  return requestJson<AssetListItem[]>('/api/assets');
}


export function fetchAssetDetail(assetId: string): Promise<AssetDetail> {
  return requestJson<AssetDetail>(`/api/assets/${assetId}`);
}


export function fetchAssetPdfMeta(assetId: string): Promise<AssetPdfDescriptor> {
  return requestJson<AssetPdfDescriptor>(`/api/assets/${assetId}/pdf-meta`);
}


export function getAssetPdfUrl(assetId: string): string {
  return `${API_BASE_URL}/api/assets/${assetId}/pdf`;
}


export function fetchAssetParseStatus(assetId: string): Promise<AssetParseStatusResponse> {
  return requestJson<AssetParseStatusResponse>(`/api/assets/${assetId}/status`);
}


export function fetchAssetParsedDocument(assetId: string): Promise<AssetParsedDocumentResponse> {
  return requestJson<AssetParsedDocumentResponse>(`/api/assets/${assetId}/parsed-json`);
}


export async function uploadAsset(file: File, title?: string): Promise<AssetUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  if (title && title.trim()) {
    formData.append('title', title.trim());
  }

  const response = await requestWithTimeout(
    `${API_BASE_URL}/api/assets/upload`,
    {
      method: 'POST',
      body: formData,
    },
    UPLOAD_REQUEST_TIMEOUT_MS,
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `上传失败：${response.status}`);
  }

  return response.json() as Promise<AssetUploadResponse>;
}


export async function retryAssetParse(assetId: string): Promise<AssetParseRetryResponse> {
  const response = await requestWithTimeout(`${API_BASE_URL}/api/assets/${assetId}/parse/retry`, {
    method: 'POST',
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `重试解析失败：${response.status}`);
  }

  return response.json() as Promise<AssetParseRetryResponse>;
}


export function previewAnchor(assetId: string, payload: AnchorPreviewRequest): Promise<AnchorPreviewResponse> {
  return postJson<AnchorPreviewResponse>(`/api/assets/${assetId}/anchor-preview`, payload);
}

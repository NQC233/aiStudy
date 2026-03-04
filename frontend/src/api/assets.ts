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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';


async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }

  return response.json() as Promise<T>;
}


export function fetchAssets(): Promise<AssetListItem[]> {
  return requestJson<AssetListItem[]>('/api/assets');
}


export function fetchAssetDetail(assetId: string): Promise<AssetDetail> {
  return requestJson<AssetDetail>(`/api/assets/${assetId}`);
}


export function fetchAssetParseStatus(assetId: string): Promise<AssetParseStatusResponse> {
  return requestJson<AssetParseStatusResponse>(`/api/assets/${assetId}/status`);
}


export async function uploadAsset(file: File, title?: string): Promise<AssetUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  if (title && title.trim()) {
    formData.append('title', title.trim());
  }

  const response = await fetch(`${API_BASE_URL}/api/assets/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `上传失败：${response.status}`);
  }

  return response.json() as Promise<AssetUploadResponse>;
}


export async function retryAssetParse(assetId: string): Promise<AssetParseRetryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/assets/${assetId}/parse/retry`, {
    method: 'POST',
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `重试解析失败：${response.status}`);
  }

  return response.json() as Promise<AssetParseRetryResponse>;
}

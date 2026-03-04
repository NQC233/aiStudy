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

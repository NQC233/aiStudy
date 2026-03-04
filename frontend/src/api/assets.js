const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
async function requestJson(path) {
    const response = await fetch(`${API_BASE_URL}${path}`);
    if (!response.ok) {
        throw new Error(`请求失败：${response.status}`);
    }
    return response.json();
}
export function fetchAssets() {
    return requestJson('/api/assets');
}
export function fetchAssetDetail(assetId) {
    return requestJson(`/api/assets/${assetId}`);
}
export function fetchAssetParseStatus(assetId) {
    return requestJson(`/api/assets/${assetId}/status`);
}
export async function uploadAsset(file, title) {
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
    return response.json();
}
export async function retryAssetParse(assetId) {
    const response = await fetch(`${API_BASE_URL}/api/assets/${assetId}/parse/retry`, {
        method: 'POST',
    });
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `重试解析失败：${response.status}`);
    }
    return response.json();
}

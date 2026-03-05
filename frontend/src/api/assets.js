const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
async function requestJson(path) {
    const response = await fetch(`${API_BASE_URL}${path}`);
    if (!response.ok) {
        throw new Error(`请求失败：${response.status}`);
    }
    return response.json();
}
async function postJson(path, payload) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
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
    return response.json();
}
export function fetchAssets() {
    return requestJson('/api/assets');
}
export function fetchAssetDetail(assetId) {
    return requestJson(`/api/assets/${assetId}`);
}
export function fetchAssetPdfMeta(assetId) {
    return requestJson(`/api/assets/${assetId}/pdf-meta`);
}
export function getAssetPdfUrl(assetId) {
    return `${API_BASE_URL}/api/assets/${assetId}/pdf`;
}
export function fetchAssetParseStatus(assetId) {
    return requestJson(`/api/assets/${assetId}/status`);
}
export function fetchAssetParsedDocument(assetId) {
    return requestJson(`/api/assets/${assetId}/parsed-json`);
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
export function previewAnchor(assetId, payload) {
    return postJson(`/api/assets/${assetId}/anchor-preview`, payload);
}

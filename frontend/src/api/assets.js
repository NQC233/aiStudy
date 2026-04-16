const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const DEFAULT_REQUEST_TIMEOUT_MS = 10000;
const UPLOAD_REQUEST_TIMEOUT_MS = 180000;
const PARSED_JSON_REQUEST_TIMEOUT_MS = 30000;
async function requestWithTimeout(input, init, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
        controller.abort();
    }, timeoutMs);
    try {
        return await fetch(input, {
            ...init,
            signal: controller.signal,
        });
    }
    catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('请求超时，请检查后端服务或资源地址。');
        }
        throw error;
    }
    finally {
        window.clearTimeout(timer);
    }
}
async function parseErrorMessage(response, fallback) {
    try {
        const payload = (await response.json());
        if (typeof payload?.detail === 'string' && payload.detail.trim()) {
            return payload.detail;
        }
    }
    catch {
        // ignore
    }
    try {
        const text = (await response.text()).trim();
        if (text) {
            return text;
        }
    }
    catch {
        // ignore
    }
    return fallback;
}
async function requestJson(path) {
    const response = await requestWithTimeout(`${API_BASE_URL}${path}`);
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
    }
    return response.json();
}
async function postJson(path, payload) {
    const response = await requestWithTimeout(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
    }
    return response.json();
}
async function patchJson(path, payload) {
    const response = await requestWithTimeout(`${API_BASE_URL}${path}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
    }
    return response.json();
}
async function deleteJson(path) {
    const response = await requestWithTimeout(`${API_BASE_URL}${path}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
    }
    return response.json();
}
export function fetchAssets() {
    return requestJson('/api/assets');
}
export function fetchAssetDetail(assetId) {
    return requestJson(`/api/assets/${assetId}`);
}
export function deleteAsset(assetId) {
    return deleteJson(`/api/assets/${assetId}`);
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
    return (async () => {
        const path = `/api/assets/${assetId}/parsed-json`;
        const attemptFetch = async (timeoutMs) => {
            const response = await requestWithTimeout(`${API_BASE_URL}${path}`, undefined, timeoutMs);
            if (!response.ok) {
                throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
            }
            return response.json();
        };
        try {
            return await attemptFetch(PARSED_JSON_REQUEST_TIMEOUT_MS);
        }
        catch (error) {
            const message = error instanceof Error ? error.message : '';
            if (!message.includes('请求超时')) {
                throw error;
            }
            return attemptFetch(PARSED_JSON_REQUEST_TIMEOUT_MS + 15000);
        }
    })();
}
export async function uploadAsset(file, title) {
    const formData = new FormData();
    formData.append('file', file);
    if (title && title.trim()) {
        formData.append('title', title.trim());
    }
    const response = await requestWithTimeout(`${API_BASE_URL}/api/assets/upload`, {
        method: 'POST',
        body: formData,
    }, UPLOAD_REQUEST_TIMEOUT_MS);
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `上传失败：${response.status}`));
    }
    return response.json();
}
export async function retryAssetParse(assetId) {
    const response = await requestWithTimeout(`${API_BASE_URL}/api/assets/${assetId}/parse/retry`, {
        method: 'POST',
    });
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `重试解析失败：${response.status}`));
    }
    return response.json();
}
export function fetchAssetMindmap(assetId) {
    return requestJson(`/api/assets/${assetId}/mindmap`);
}
export async function rebuildAssetMindmap(assetId) {
    const response = await requestWithTimeout(`${API_BASE_URL}/api/assets/${assetId}/mindmap/rebuild`, {
        method: 'POST',
    });
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `重建导图失败：${response.status}`));
    }
    return response.json();
}
export function previewAnchor(assetId, payload) {
    return postJson(`/api/assets/${assetId}/anchor-preview`, payload);
}
export function createAssetNote(assetId, payload) {
    return postJson(`/api/assets/${assetId}/notes`, payload);
}
export function fetchAssetNotes(assetId, anchorType) {
    const query = anchorType ? `?anchor_type=${encodeURIComponent(anchorType)}` : '';
    return requestJson(`/api/assets/${assetId}/notes${query}`);
}
export function updateNote(noteId, payload) {
    return patchJson(`/api/notes/${noteId}`, payload);
}
export function deleteNote(noteId) {
    return deleteJson(`/api/notes/${noteId}`);
}
export function createAssetChatSession(assetId, title) {
    return postJson(`/api/assets/${assetId}/chat/sessions`, {
        title: title?.trim() || null,
    });
}
export function fetchAssetChatSessions(assetId) {
    return requestJson(`/api/assets/${assetId}/chat/sessions`);
}
export function fetchChatSessionMessages(sessionId) {
    return requestJson(`/api/chat/sessions/${sessionId}/messages`);
}
export function sendChatSessionMessage(sessionId, payload) {
    return postJson(`/api/chat/sessions/${sessionId}/messages`, payload);
}
export function fetchAssetSlides(assetId) {
    return requestJson(`/api/assets/${assetId}/slides`);
}
export function rebuildAssetSlides(assetId) {
    return postJson(`/api/assets/${assetId}/slides/runtime-bundle/rebuild`, {});
}
export function ensureAssetSlideTts(assetId, payload) {
    return postJson(`/api/assets/${assetId}/slides/tts/ensure`, payload);
}
export function retryNextAssetSlideTts(assetId, payload) {
    return postJson(`/api/assets/${assetId}/slides/tts/retry-next`, payload);
}

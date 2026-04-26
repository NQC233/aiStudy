const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const ACCESS_TOKEN_STORAGE_KEY = 'paper-learning-access-token';
function readDetailMessage(payload) {
    if (typeof payload !== 'object' || payload === null) {
        return null;
    }
    const detail = payload.detail;
    return typeof detail === 'string' && detail.trim() ? detail : null;
}
async function parseErrorMessage(response, fallback) {
    try {
        const payload = await response.json();
        const detail = readDetailMessage(payload);
        if (detail) {
            return detail;
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
export function readStoredAccessToken() {
    return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
}
export function storeAccessToken(accessToken) {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken);
}
export function clearStoredAccessToken() {
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}
export function getAuthorizationHeaderValue() {
    const accessToken = readStoredAccessToken();
    return accessToken ? `Bearer ${accessToken}` : null;
}
export async function login(payload) {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `登录失败：${response.status}`));
    }
    return response.json();
}
export async function register(payload) {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `注册失败：${response.status}`));
    }
    return response.json();
}
export async function fetchCurrentUser() {
    const authorization = getAuthorizationHeaderValue();
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
        headers: authorization ? { Authorization: authorization } : undefined,
    });
    if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `获取当前用户失败：${response.status}`));
    }
    return response.json();
}

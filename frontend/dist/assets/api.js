let csrfToken = '';
export const setCsrf = (token) => { csrfToken = token; };
export class ApiError extends Error {
    status;
    constructor(status, message) {
        super(message);
        this.status = status;
        this.name = 'ApiError';
    }
}
export async function api(path, method = 'GET', body, extraHeaders) {
    const headers = { ...extraHeaders };
    const multipart = body instanceof FormData;
    if (body !== undefined && !multipart)
        headers['Content-Type'] = 'application/json';
    if (!['GET', 'HEAD'].includes(method) && csrfToken)
        headers['X-CSRF-Token'] = csrfToken;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90_000);
    try {
        const response = await fetch(path, { method, credentials: 'same-origin', headers, cache: 'no-store',
            body: body === undefined ? undefined : multipart ? body : JSON.stringify(body), signal: controller.signal });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const object = data;
            const text = typeof object.detail === 'string' ? object.detail : 'Požiadavku sa nepodarilo dokončiť.';
            throw new ApiError(response.status, text + (object.request_id ? ` ID: ${object.request_id}` : ''));
        }
        return data;
    }
    catch (error) {
        if (error instanceof ApiError)
            throw error;
        if (error instanceof DOMException && error.name === 'AbortError')
            throw new ApiError(0, 'Požiadavka trvala príliš dlho. Pri nahrávaní skúste ten istý súbor znova; kľúč zostane zachovaný.');
        throw new ApiError(0, 'Spojenie so serverom nie je dostupné. Skontrolujte sieť a skúste to znova.');
    }
    finally {
        clearTimeout(timeout);
    }
}

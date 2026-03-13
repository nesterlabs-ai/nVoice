// Runtime configuration - this file is overwritten by docker-entrypoint.sh in production.
// For local development, backend URL is now controlled via `client/src/config.ts`.
// Keeping this commented so `getBackendUrl()` falls back to the config.ts values.
// window.__BACKEND_URL__ = "http://localhost:7860";
window.LIGHTRAG_URL = "https://lightrag.nesterlabs.com";
window.LIGHTRAG_API_KEY = "FsJr02HwFayUuApjK3YOjdVwE1UWhyuC";

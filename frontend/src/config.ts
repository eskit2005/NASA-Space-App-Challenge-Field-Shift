// API & environment configuration
// Set VITE_MOCK_API=false in .env.local to use the live backend API by default

export const DEFAULT_MOCK_API = import.meta.env.VITE_MOCK_API !== 'false';
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

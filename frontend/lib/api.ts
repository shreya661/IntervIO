/**
 * Centralized API configuration for InterviewOne AI Frontend.
 * Reads NEXT_PUBLIC_API_URL from environment when deployed (e.g. Vercel/Railway),
 * falling back to local FastAPI development server.
 */
export const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

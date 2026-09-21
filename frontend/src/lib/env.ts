import { z } from 'zod';

// The deployment's reverse proxy mounts the API under this prefix on the app's own origin.
const SAME_ORIGIN_API_PREFIX = '/api';

// A shipped bundle must address its own origin, never a developer machine: a compiled-in
// loopback origin makes every visitor's browser call their own localhost (2026-09-21 outage).
// `npm run check:api-origin` asserts this on the built artifact and CI runs it before deploy.
const fallbackBaseUrl = import.meta.env.PROD
  ? `${window.location.origin}${SAME_ORIGIN_API_PREFIX}`
  : 'http://localhost:8000';

// An explicit VITE_API_BASE_URL always wins: the isolated E2E harness passes its own loopback
// origin and local development points at the local backend. The dev fallback above lives in
// the non-PROD branch only, which Vite folds away in a production build.
const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url(),
});

const parsed = envSchema.safeParse({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL ?? fallbackBaseUrl,
});

if (!parsed.success) {
  throw new Error(`Invalid frontend environment: ${parsed.error.message}`);
}

export const env = {
  apiBaseUrl: parsed.data.VITE_API_BASE_URL,
} as const;

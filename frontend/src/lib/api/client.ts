import createClient from 'openapi-fetch';
import type { paths } from '@/types/api';
import { env } from '@/lib/env';

// The backend FastAPI OpenAPI schema is the contract source between frontend and
// backend. `paths` is generated from it via `npm run api:generate` (requires the
// backend running at VITE_API_BASE_URL). See docs/FRONTEND_ARCHITECTURE.md §API contract.
//
// All API access must go through this typed client — never fetch('/api/...') in
// components, and never hand-write backend DTO interfaces.
export const apiClient = createClient<paths>({ baseUrl: env.apiBaseUrl, credentials: 'include' });

/** Resolves a backend-normalized public resource without losing an API base pathname. */
export function resolveApiResourceUrl(resourceUrl: string, apiBaseUrl = env.apiBaseUrl) {
  const base = new URL(apiBaseUrl);
  const basePath = base.pathname.replace(/\/$/, '');
  const resourcePath = resourceUrl.startsWith('/') ? resourceUrl : `/${resourceUrl}`;
  return new URL(`${basePath}${resourcePath}`, base.origin).toString();
}

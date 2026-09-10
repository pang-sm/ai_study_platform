import { z } from 'zod';

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url().default('http://localhost:8000'),
});

const parsed = envSchema.safeParse(import.meta.env);

if (!parsed.success) {
  throw new Error(`Invalid frontend environment: ${parsed.error.message}`);
}

export const env = {
  apiBaseUrl: parsed.data.VITE_API_BASE_URL,
} as const;

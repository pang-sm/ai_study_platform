import { z } from 'zod';

/**
 * The backend's `user_profile()` serializer answers as a raw dict, so the OpenAPI document types
 * every response that carries it (login, register, `/me`, `/me/profile`) as `unknown`. This
 * reader declares the SUBSET of that serializer this UI renders — every field below was read out
 * of `user_profile()` itself, and none was invented. Unknown keys are dropped rather than
 * surfaced, so a field the backend stops sending reads as absent instead of as a stale value.
 *
 * `user_profile` nests under different keys per endpoint (`{user}` vs `{profile}`), so the two
 * envelopes are exported separately.
 */
export const userProfileSchema = z.object({
  id: z.number().optional(),
  username: z.string(),
  nickname: z.string().optional(),
  avatar: z.string().optional(),
  avatar_url: z.string().nullable().optional(),
  is_admin: z.boolean().optional(),
  plan: z.string().optional(),
  plan_source: z.string().optional(),
  plan_expires_at: z.string().nullable().optional(),
  onboarding_completed: z.boolean().optional(),
  needs_onboarding: z.boolean().optional(),
  email: z.string().optional(),
  email_verified: z.boolean().optional(),
  phone: z.string().optional(),
  phone_verified: z.boolean().optional(),
  grade: z.string().optional(),
  major: z.string().optional(),
  semester: z.string().optional(),
  school: z.string().optional(),
  learning_direction: z.string().optional(),
  learning_stage: z.string().optional(),
  daily_study_minutes: z.number().optional(),
  ai_answer_style: z.string().optional(),
  answer_detail_level: z.string().optional(),
  material_reference_preference: z.string().optional(),
  focus_courses: z.string().optional(),
  created_at: z.string().nullable().optional(),
});

export const meEnvelopeSchema = z.object({ user: userProfileSchema });
export const profileEnvelopeSchema = z.object({ profile: userProfileSchema });

export type AuthUser = z.infer<typeof userProfileSchema>;
export type UserProfile = z.infer<typeof userProfileSchema>;

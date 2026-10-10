/** Navigation destinations shared by the desktop list and mobile selector. */
export const SECTION_LIST = [
  { id: 'profile-personal', label: '个人资料', to: '/profile', section: 'profile-personal' },
  { id: 'profile-learning', label: '学习设置', to: '/profile', section: 'profile-learning' },
  { id: 'profile-security', label: '账号安全', to: '/profile', section: 'profile-security' },
  { id: 'terms', label: '法务', to: '/terms' },
] as const;

/** IDs that correspond to sections rendered within the personal center. */
export const SECTION_IDS: readonly string[] = SECTION_LIST.flatMap((item) =>
  item.to === '/profile' ? [item.section] : [],
);

/** The section a setup flow should send a learner back to when it was entered from 学习设置. */
export const LEARNING_SECTIONS_ANCHOR = '/profile?section=profile-learning';

export function isProfileSectionId(value: string): boolean {
  return SECTION_IDS.includes(value);
}

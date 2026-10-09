/**
 * The档案's sections, grouped, as one declaration.
 *
 * The groups mirror how a learner thinks about the page — who I am, what I have, how to get back
 * in — and the section list is generated from this same declaration, so a section that exists is
 * always listed and a listed section always exists.
 *
 * It lives apart from the page because the route needs the id vocabulary to validate the
 * `section` search param, and a route must be able to answer "is this a real section?" without
 * pulling in the whole component tree.
 */
export type ProfileSection = { id: string; label: string };

export const SECTION_LIST: readonly ProfileSection[] = [
  { id: 'profile-personal', label: '个人资料' },
  { id: 'profile-learning', label: '学习设置' },
  { id: 'profile-membership', label: '会员与额度' },
  { id: 'profile-data', label: '学习数据' },
  { id: 'profile-security', label: '账号安全' },
  { id: 'profile-legal', label: '法务' },
];

/** The same declaration as a stable list of ids, which is what the scroll observer keys on. */
export const SECTION_IDS: readonly string[] = SECTION_LIST.map((section) => section.id);

/** The section a setup flow should send a learner back to when it was entered from 学习设置. */
export const LEARNING_SECTIONS_ANCHOR = '/profile?section=learning';

export function isProfileSectionId(value: string): boolean {
  return SECTION_IDS.includes(value);
}

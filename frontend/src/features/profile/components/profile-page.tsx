import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { useAuth } from '@/features/auth/auth-context';
import { useLogout } from '@/features/auth/api/auth';
import { useProfile } from '../api/profile';
import { LearningSettingsForm, PersonalInfoForm } from './profile-settings';
import { LearningSpacesSection } from './profile-learning-spaces';
import { SubscriptionSection, UsageSection } from './profile-membership';
import { cn } from '@/lib/utils';
import { EmailSection, PasswordForm, PhoneSection } from './profile-security';

const LEARNING_DATA_ENTRIES = [
  { to: '/reports', label: '学习报告', description: '按学习空间查看已完成的学习与练习记录。' },
  { to: '/review', label: '统一复习', description: '跨学习空间的待复习与待处理项目。' },
  { to: '/exam', label: '考研学习记录', description: '练习、真题、错题与计划完成情况。' },
  { to: '/course', label: '课程学习记录', description: '已学内容与课程练习记录。' },
  { to: '/programming', label: '编程学习记录', description: '练习提交、运行与测试结果。' },
] as const;

/**
 * The档案's sections, grouped, as one page.
 *
 * The groups mirror how a learner thinks about the page — who I am, what I have, how to get back
 * in — and the section list on the left is generated from this same declaration, so a section
 * that exists is always listed and a listed section always exists. Groups are typed the same way
 * the rest of the product types structure: a small letter-spaced label above the content, not a
 * card around it.
 */
type ProfileSection = { id: string; label: string };
type ProfileSectionGroup = { id: string; label: string; sections: readonly ProfileSection[] };

const SECTION_GROUPS: readonly ProfileSectionGroup[] = [
  {
    id: 'identity',
    label: '身份与学习设置',
    sections: [
      { id: 'profile-personal', label: '个人信息' },
      { id: 'profile-learning', label: '学习设置' },
    ],
  },
  {
    id: 'entitlement',
    label: '会员与额度',
    sections: [
      { id: 'profile-membership', label: '会员' },
      { id: 'profile-usage', label: '用量' },
    ],
  },
  {
    id: 'records',
    label: '学习记录',
    sections: [{ id: 'profile-data', label: '学习数据' }],
  },
  {
    id: 'account',
    label: '账号',
    sections: [
      { id: 'profile-security', label: '账号与安全' },
      { id: 'profile-legal', label: '法务' },
    ],
  },
];

const SECTION_LIST: readonly ProfileSection[] = SECTION_GROUPS.flatMap((group) => group.sections);
/** The same declaration as a stable list of ids, which is what the scroll observer keys on. */
const SECTION_IDS: readonly string[] = SECTION_LIST.map((section) => section.id);

/** Read the heading off the declaration, so a group cannot be listed under one name and titled another. */
function groupLabel(id: string): string {
  return SECTION_GROUPS.find((group) => group.id === id)?.label ?? id;
}

function SectionGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="border-t border-border-default pt-8 first:border-t-0 first:pt-0">
      <h2 className="text-metadata font-medium tracking-eyebrow text-text-muted">{label}</h2>
      <div className="mt-6 space-y-10">{children}</div>
    </section>
  );
}

function Section({ id, title, description, children }: { id: string; title: string; description?: string; children: ReactNode }) {
  // The anchor target and the heading's own id are different elements: naming the section by its
  // heading only works while `aria-labelledby` points somewhere other than the section itself.
  const headingId = `${id}-title`;
  return (
    <section aria-labelledby={headingId} id={id} className="scroll-mt-24">
      <h3 id={headingId} className="text-card-title font-semibold text-text-primary">
        {title}
      </h3>
      {description ? <p className="mt-1 max-w-prose text-body text-text-secondary">{description}</p> : null}
      {/* A form measure, not the width of the column: an input as wide as a 1280px page is
          harder to read back than one the eye can take in at a glance. */}
      <div className="mt-5 max-w-2xl">{children}</div>
    </section>
  );
}

/**
 * The same sections, reachable from a control narrow enough for a phone. A native select is the
 * one selector every device already knows how to operate, including with a screen reader, and it
 * names every section without a horizontally scrolling strip. Scrolling is best-effort: where the
 * environment does not implement it, the sections are still stacked in the same order below.
 */
function SectionSelector() {
  const [selected, setSelected] = useState('');

  const jumpTo = (id: string) => {
    setSelected(id);
    const target = document.getElementById(id);
    if (target && typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ block: 'start' });
    }
  };

  return (
    <div className="lg:hidden">
      <label htmlFor="profile-section-selector" className="block text-metadata font-medium text-text-secondary">
        跳转到分区
      </label>
      <select
        id="profile-section-selector"
        value={selected}
        onChange={(event) => jumpTo(event.target.value)}
        className="mt-2 h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        <option value="">选择要查看的分区…</option>
        {SECTION_LIST.map((section) => (
          <option key={section.id} value={section.id}>
            {section.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function ProfileSkeleton() {
  return (
    <div className="space-y-4" aria-hidden="true">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="h-4 w-64" />
      <Skeleton className="h-11 w-full" />
      <Skeleton className="h-11 w-full" />
    </div>
  );
}

/**
 * Which section the reader is currently in, for the desktop section list.
 *
 * The list is an anchor list, so "current" is a scroll position rather than a route. A section
 * counts as current from the moment its heading reaches the top of the reading area until the
 * next one does — measured against the sticky nav's own height, so a section is marked while the
 * reader is actually inside it rather than one section late.
 */
function useCurrentSection(ids: readonly string[]): string | undefined {
  const [current, setCurrent] = useState<string | undefined>(ids[0]);

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    const sections = ids.flatMap((id) => {
      const element = document.getElementById(id);
      return element ? [{ id, element }] : [];
    });
    if (!sections.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entered = entries.filter((entry) => entry.isIntersecting);
        if (!entered.length) return;
        const top = Math.min(...entered.map((entry) => entry.boundingClientRect.top));
        const match = entered.find((entry) => entry.boundingClientRect.top === top);
        const id = match?.target.id;
        if (id) setCurrent(id);
      },
      { rootMargin: '-96px 0px -60% 0px', threshold: 0 },
    );
    sections.forEach((section) => observer.observe(section.element));
    return () => observer.disconnect();
  }, [ids]);

  return current;
}

export function ProfilePage() {
  const profile = useProfile();
  const auth = useAuth();
  const logout = useLogout();
  const navigate = useNavigate();
  const current = useCurrentSection(SECTION_IDS);

  /**
   * The editable sections wait for the stored profile rather than starting from the session's
   * copy of it. A form's defaults are read once, at mount, so mounting on the partial session
   * value would leave every field showing a stale value after the real one arrived.
   */
  const user = profile.data;

  const onLogout = async () => {
    try {
      await logout.mutateAsync();
    } finally {
      // The guard is the single authority: once the session cache reads `null`, every protected
      // route would send this visitor to the sign-in screen on its own. Navigating explicitly
      // just gets them there without waiting for the next click.
      await navigate({ to: '/login' });
    }
  };

  const identity = user ?? auth.user;

  return (
    <div className="mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
      <header>
        <p className="text-metadata font-medium tracking-eyebrow text-text-muted">个人学习档案</p>
        <h1 className="mt-2 text-page-title font-semibold text-text-primary">学习档案</h1>
      </header>

      {profile.isError ? (
        <StatusNote tone="danger" className="mt-8">
          学习档案暂时无法加载，请稍后重试。
        </StatusNote>
      ) : null}

      {!profile.isError && !identity ? (
        <div className="mt-8">
          <ProfileSkeleton />
        </div>
      ) : null}

      {identity ? (
        <div className="mt-8 lg:grid lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-12">
          <nav aria-label="学习档案分区" className="hidden lg:block">
            <div className="sticky top-24">
              {SECTION_GROUPS.map((group) => (
                <div key={group.id} className="mt-6 first:mt-0">
                  <p className="text-metadata font-medium tracking-eyebrow text-text-muted">
                    {group.label}
                  </p>
                  <ul className="mt-2 space-y-0.5">
                    {group.sections.map((section) => (
                      <li key={section.id}>
                        <a
                          href={`#${section.id}`}
                          aria-current={current === section.id ? 'true' : undefined}
                          className={cn(
                            'block rounded-control border-l-2 px-2 py-1.5 text-body hover:bg-primary-soft hover:text-text-primary',
                            current === section.id
                              ? 'border-primary bg-primary-soft font-medium text-primary-ink'
                              : 'border-transparent text-text-secondary',
                          )}
                        >
                          {section.label}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </nav>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border-default pb-6">
              <p className="text-card-title font-medium text-text-primary">
                {identity.nickname || identity.username}
              </p>
              <p className="text-body text-text-secondary">账号：{identity.username}</p>
              {auth.user?.needs_onboarding ? <Badge tone="warning">学习设置未完成</Badge> : null}
            </div>

            {!user ? (
              <div className="pt-8">
                <ProfileSkeleton />
              </div>
            ) : (
              <div className="mt-8 space-y-10">
                <SectionSelector />

                <SectionGroup label={groupLabel('identity')}>
                  <Section id="profile-personal" title="个人信息" description="昵称、年级、专业与学期。">
                    <PersonalInfoForm profile={user} />
                  </Section>

                  <Section
                    id="profile-learning"
                    title="学习设置"
                    description="三个学习空间的当前设置，直接读自各学习空间；要修改就进入对应空间的设置流程。备考计划的每日时长与复习策略由学习计划页面管理。"
                  >
                    <LearningSpacesSection />
                    <div className="mt-8 border-t border-border-default pt-6">
                      <h4 className="text-body font-medium text-text-primary">学习方向</h4>
                      <div className="mt-4">
                        <LearningSettingsForm profile={user} />
                      </div>
                    </div>
                    <p className="mt-5 text-body text-text-secondary">
                      备考计划的时长与复习策略在{' '}
                      {/*
                        A link inside running text is underlined, not merely coloured: the ink
                        blue and the surrounding grey are too close in contrast for colour alone
                        to mark it (WCAG 1.4.1), which axe flags as link-in-text-block.
                      */}
                      <Link
                        to="/exam/cs408/plan"
                        className="text-primary-ink underline hover:text-primary-hover"
                      >
                        学习计划
                      </Link>{' '}
                      中设置。
                    </p>
                  </Section>
                </SectionGroup>

                <SectionGroup label={groupLabel('entitlement')}>
                  <Section id="profile-membership" title="会员" description="当前档位与额度上限。">
                    <SubscriptionSection />
                  </Section>

                  <Section id="profile-usage" title="用量" description="来自服务端账本的真实额度使用情况。">
                    <UsageSection />
                  </Section>
                </SectionGroup>

                <SectionGroup label={groupLabel('records')}>
                  <Section id="profile-data" title="学习数据" description="你的学习记录入口。">
                    <ul className="space-y-4">
                      {LEARNING_DATA_ENTRIES.map((entry) => (
                        <li key={entry.to}>
                          <Link to={entry.to} className="text-body text-primary-ink hover:text-primary-hover">
                            {entry.label}
                          </Link>
                          <p className="mt-1 text-body text-text-secondary">{entry.description}</p>
                        </li>
                      ))}
                    </ul>
                  </Section>
                </SectionGroup>

                <SectionGroup label={groupLabel('account')}>
                  <Section id="profile-security" title="账号与安全" description="密码、邮箱与手机号。">
                    <div className="space-y-8">
                      <div>
                        <h4 className="text-body font-medium text-text-primary">修改密码</h4>
                        <div className="mt-4">
                          <PasswordForm />
                        </div>
                      </div>
                      <div>
                        <h4 className="text-body font-medium text-text-primary">绑定邮箱</h4>
                        <div className="mt-4">
                          <EmailSection profile={user} />
                        </div>
                      </div>
                      <div>
                        <h4 className="text-body font-medium text-text-primary">手机号</h4>
                        <div className="mt-4">
                          <PhoneSection profile={user} />
                        </div>
                      </div>
                    </div>
                  </Section>

                  <Section id="profile-legal" title="法务">
                    <p className="text-body text-text-secondary">
                      当前版本尚未发布用户协议与隐私政策，因此这里不提供对应入口。
                    </p>
                  </Section>
                </SectionGroup>

                <section aria-labelledby="profile-logout" className="border-t border-border-default pt-8">
                  <h2 id="profile-logout" className="text-card-title font-semibold text-text-primary">
                    退出登录
                  </h2>
                  <p className="mt-1 text-body text-text-secondary">
                    退出后本机缓存的账号学习数据会被清除。
                  </p>
                  <Button
                    variant="secondary"
                    className="mt-5"
                    onClick={onLogout}
                    disabled={logout.isPending}
                  >
                    {logout.isPending ? '正在退出…' : '退出登录'}
                  </Button>
                </section>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

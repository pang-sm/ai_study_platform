import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate, useSearch } from '@tanstack/react-router';
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
import { groupLabel, SECTION_GROUPS, SECTION_IDS, SECTION_LIST } from './profile-sections';

const LEARNING_DATA_ENTRIES = [
  { to: '/reports', label: '学习报告', description: '按方向查看已完成的学习与练习记录。' },
  { to: '/review', label: '统一复习', description: '各个方向汇总在一起的待复习与待处理项目。' },
  { to: '/exam', label: '考研学习记录', description: '练习、真题、错题与计划完成情况。' },
  { to: '/course', label: '专业学习记录', description: '已学内容与课程练习记录。' },
  { to: '/programming', label: '编程学习记录', description: '练习提交、运行与测试结果。' },
] as const;

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
 * The same sections, reachable from a control narrow enough for a phone.
 *
 * It is a native select because that is the one selector every device already knows how to
 * operate, including with a screen reader. Choosing a section navigates, exactly as the wide
 * screen's list does, so the address bar says which section is open on both layouts.
 */
function SectionSelector() {
  const navigate = useNavigate();
  const { section } = useSearch({ from: '/profile' });

  return (
    <div className="lg:hidden">
      <label htmlFor="profile-section-selector" className="block text-body font-medium text-text-primary">
        跳转到
      </label>
      <select
        id="profile-section-selector"
        value={section ?? ''}
        onChange={(event) => {
          void navigate({ to: '/profile', search: { section: event.target.value || undefined } });
        }}
        className="mt-2 h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        <option value="">选择要查看的分区…</option>
        {SECTION_LIST.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label}
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
function useCurrentSection(ids: readonly string[], requested?: string): string | undefined {
  const [current, setCurrent] = useState<string | undefined>(requested ?? ids[0]);

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
  const { section } = useSearch({ from: '/profile' });
  const current = useCurrentSection(SECTION_IDS, section);

  /**
   * The editable sections wait for the stored profile rather than starting from the session's
   * copy of it. A form's defaults are read once, at mount, so mounting on the partial session
   * value would leave every field showing a stale value after the real one arrived.
   */
  const user = profile.data;

  /**
   * A `section` in the address bar is a learner who asked for that section, not for the top of
   * the page — so arriving here from a setup flow's 返回 lands on 学习设置 rather than on 个人信息.
   *
   * It waits on the profile because the sections do not exist until it has loaded; scrolling in
   * the same tick as the navigation would find nothing and silently leave the reader at the top,
   * which is exactly the bug this replaces.
   */
  useEffect(() => {
    if (!section || !user) return;
    const target = document.getElementById(section);
    if (!target || typeof target.scrollIntoView !== 'function') return;
    target.scrollIntoView({ block: 'start' });
  }, [section, user]);

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
                    {group.sections.map((item) => (
                      <li key={item.id}>
                        <Link
                          to="/profile"
                          search={{ section: item.id }}
                          aria-current={current === item.id ? 'true' : undefined}
                          className={cn(
                            'block rounded-control border-l-2 px-2 py-1.5 text-body hover:bg-primary-soft hover:text-text-primary',
                            current === item.id
                              ? 'border-primary bg-primary-soft font-medium text-primary-ink'
                              : 'border-transparent text-text-secondary',
                          )}
                        >
                          {item.label}
                        </Link>
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
                    description="三个方向的当前设置；要修改就进入各自的方向设置。备考计划的每日时长与复习策略在学习计划页面里管理。"
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

                  <Section id="profile-usage" title="用量" description="你的额度使用情况。">
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
                    <ul className="space-y-4">
                      <li>
                        <Link to="/terms" className="text-body text-primary-ink hover:text-primary-hover">
                          用户协议
                        </Link>
                        <p className="mt-1 text-body text-text-secondary">使用本服务的约定与双方责任。</p>
                      </li>
                      <li>
                        <Link to="/privacy" className="text-body text-primary-ink hover:text-primary-hover">
                          隐私政策
                        </Link>
                        <p className="mt-1 text-body text-text-secondary">收集哪些信息、如何使用与保存。</p>
                      </li>
                    </ul>
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

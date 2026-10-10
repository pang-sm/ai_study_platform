import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate, useRouterState, useSearch } from '@tanstack/react-router';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { useAuth } from '@/features/auth/auth-context';
import { useProfile } from '../api/profile';
import { LearningSettingsForm, PersonalInfoForm } from './profile-settings';
import { LearningSpacesSection } from './profile-learning-spaces';
import { cn } from '@/lib/utils';
import { EmailSection, LogoutButton, PasswordForm } from './profile-security';
import { SECTION_IDS, SECTION_LIST } from './profile-sections';

function SectionGroup({ children }: { label?: string; children: ReactNode }) {
  return (
    <section className="border-t border-border-default pt-6 first:border-t-0 first:pt-0">
      <div className="space-y-8">{children}</div>
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

function scrollToProfileSection(id: string) {
  const target = document.getElementById(id);
  if (typeof target?.scrollIntoView !== 'function') return;
  target.scrollIntoView({ block: 'start', behavior: 'auto' });
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
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const selected = pathname === '/profile'
    ? section ?? 'profile-personal'
    : SECTION_LIST.find((item) => item.to === pathname)?.id ?? '';

  const selectDestination = (id: string) => {
    const destination = SECTION_LIST.find((item) => item.id === id);
    if (!destination) return;
    if (destination.to === '/profile') {
      void navigate({ to: '/profile', search: { section: destination.section } }).then(() => {
        scrollToProfileSection(destination.section);
      });
    } else if (destination.to === '/terms') {
      void navigate({ to: '/terms' });
    }
  };

  return (
    <div className="lg:hidden">
      <label htmlFor="profile-section-selector" className="block text-body font-medium text-text-primary">
        跳转到
      </label>
      <select
        id="profile-section-selector"
        value={selected}
        onChange={(event) => {
          selectDestination(event.target.value);
        }}
        className="mt-2 h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
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
function useCurrentSection(ids: readonly string[], requested?: string, enabled = true): string | undefined {
  const [current, setCurrent] = useState<string | undefined>(requested ?? ids[0]);
  const navigate = useNavigate();

  useEffect(() => {
    // Wait for the stored profile before observing scroll position. On a deep-link refresh,
    // the initial viewport is still at the top while profile data loads; observing then would
    // mistake that temporary position for the learner's requested section and replace the URL.
    if (!enabled || typeof IntersectionObserver === 'undefined') return;
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
        if (id) {
          setCurrent(id);
          if (id !== requested) {
            void navigate({ to: '/profile', search: { section: id }, replace: true });
          }
        }
      },
      { rootMargin: '-96px 0px -60% 0px', threshold: 0 },
    );
    sections.forEach((section) => observer.observe(section.element));
    return () => observer.disconnect();
  }, [enabled, ids, navigate, requested]);

  return requested ?? current;
}

export function ProfilePage() {
  const profile = useProfile();
  const auth = useAuth();
  const navigate = useNavigate();
  const { section } = useSearch({ from: '/profile' });
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const current = useCurrentSection(SECTION_IDS, section, Boolean(profile.data));

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
    scrollToProfileSection(section);
  }, [section, user]);

  const identity = user ?? auth.user;

  return (
    <div className="mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-section-title font-semibold text-text-primary">个人中心</h1>
        {auth.user?.needs_onboarding ? <Badge tone="warning">学习设置未完成</Badge> : null}
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
        <div className="mt-5 lg:grid lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-10">
          <nav aria-label="学习档案分区" className="hidden lg:block">
            <div className="sticky top-24">
              <ul className="space-y-0.5">
                {SECTION_LIST.map((item) => (
                  <li key={item.id}>
                    {item.to === '/profile' ? (
                      <a
                        href={`/profile?section=${encodeURIComponent(item.section)}`}
                        onClick={(event) => {
                          if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                          event.preventDefault();
                          void navigate({ to: '/profile', search: { section: item.section } }).then(() => {
                            scrollToProfileSection(item.section);
                          });
                        }}
                        aria-current={pathname === '/profile' && current === item.section ? 'location' : undefined}
                        className={cn(
                          'block rounded-control border-l-2 px-2 py-1.5 text-body hover:bg-primary-soft hover:text-text-primary',
                          pathname === '/profile' && current === item.section
                            ? 'border-primary bg-primary-soft font-medium text-primary-ink'
                            : 'border-transparent text-text-secondary',
                        )}
                      >
                        {item.label}
                      </a>
                    ) : (
                      <Link
                        to={item.to}
                        activeOptions={{ exact: true }}
                        aria-current={pathname === item.to ? 'page' : undefined}
                        className={cn(
                          'block rounded-control border-l-2 px-2 py-1.5 text-body hover:bg-primary-soft hover:text-text-primary',
                          pathname === item.to
                            ? 'border-primary bg-primary-soft font-medium text-primary-ink'
                            : 'border-transparent text-text-secondary',
                        )}
                      >
                        {item.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </nav>

          <div className="min-w-0">
            {!user ? (
              <div className="pt-8">
                <ProfileSkeleton />
              </div>
            ) : (
              <div className="mt-6 space-y-8">
                <SectionSelector />

                <SectionGroup>
                  <Section id="profile-personal" title="个人资料">
                    <PersonalInfoForm profile={user} />
                  </Section>

                  <Section id="profile-learning" title="学习设置">
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

                <SectionGroup>
                  <Section id="profile-security" title="账号安全">
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
                        <h4 className="text-body font-medium text-text-primary">账号</h4>
                        <div className="mt-4"><LogoutButton /></div>
                      </div>
                    </div>
                  </Section>
                </SectionGroup>

              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

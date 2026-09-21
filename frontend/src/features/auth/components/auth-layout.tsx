import type { ReactNode } from 'react';
import { LEARNING_SPACES, SHARED_TOOLS } from '@/components/layout/primary-nav';

/**
 * The frame shared by sign-in and registration.
 *
 * These routes render outside `AppShell`, so they carry their own product identity. On a wide
 * screen the identity is a column of its own — the brand, what the product is, and the three
 * learning spaces it actually contains — while the form keeps a narrow measure on paper. On a
 * phone the two collapse into one column and the identity reduces to the mark plus one line,
 * because a sign-in form is the whole task there.
 *
 * The three spaces are read from the navigation's own declaration rather than retyped, so this
 * page cannot end up describing a different product than the shell does. They are shown as
 * text, not links: a visitor who cannot sign in yet would only be bounced back here.
 */
export function AuthLayout({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-page-background lg:grid lg:min-h-screen lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1fr)]">
      <aside className="bg-lab-ink px-5 py-6 text-lab-paper sm:px-10 sm:py-8 lg:px-14 lg:py-16">
        <div className="mx-auto flex h-full w-full max-w-md flex-col">
          {/*
            The mark is identity here, not navigation: every other route is behind the guard, so a
            link home would only bounce a signed-out visitor back to this screen.
          */}
          <div className="flex w-fit items-center gap-3">
            <img
              src="/brand/zhixue-v2/04_智学平台_图标标识_Icon_Only_transparent.png"
              alt=""
              className="size-8 object-contain lg:size-10"
            />
            <span className="text-card-title font-semibold">智学平台</span>
          </div>

          <p className="mt-6 max-w-sm text-body text-lab-paper-muted lg:mt-10">
            一个账号、一套用量额度，三个学习空间共用同一份学习记录。
          </p>

          <div className="mt-10 hidden lg:block">
            <p className="text-metadata font-medium tracking-eyebrow text-lab-grid-light">
              学习空间
            </p>
            <ul className="mt-4 space-y-5">
              {LEARNING_SPACES.map((space) => (
                <li key={space.to} className="flex gap-3">
                  <space.icon className="mt-0.5 size-5 shrink-0 text-lab-grid-light" aria-hidden="true" />
                  <div>
                    <p className="text-body font-medium text-lab-paper">{space.label}</p>
                    <p className="mt-1 text-metadata text-lab-grid-light">
                      {space.eyebrow} · {space.detail}
                    </p>
                  </div>
                </li>
              ))}
            </ul>

            <p className="mt-8 text-metadata font-medium tracking-eyebrow text-lab-grid-light">
              共享学习工具
            </p>
            <p className="mt-3 text-body text-lab-paper-muted">
              {SHARED_TOOLS.map((tool) => tool.label).join(' · ')}
            </p>
          </div>

          <p className="mt-auto hidden pt-12 text-metadata text-lab-grid-light lg:block">
            © 2026 ZHIXUE LEARNING LAB
          </p>
        </div>
      </aside>

      <div className="flex flex-col px-5 py-10 sm:px-10 sm:py-14 lg:px-16 lg:py-16">
        <main className="mx-auto w-full max-w-md flex-1">
          <h1 className="text-page-title font-semibold text-text-primary">{title}</h1>
          <p className="mt-3 max-w-prose text-body text-text-secondary">{description}</p>
          <div className="mt-8">{children}</div>
        </main>
        {/* Outside `main`, so it is the page's contentinfo landmark rather than a scoped footer —
            the same thing every other page's footer is. */}
        <footer className="mx-auto mt-10 w-full max-w-md border-t border-border-default pt-5 text-body text-text-secondary">
          {footer}
          <p className="mt-4 text-metadata text-text-muted">
            用户协议与隐私政策尚未发布，当前版本不提供对应入口。
          </p>
        </footer>
      </div>
    </div>
  );
}

import type { ReactNode } from 'react';
import { Link } from '@tanstack/react-router';

/**
 * The frame shared by sign-in and registration.
 *
 * These routes render outside `AppShell`, so they carry their own product identity. On a wide
 * screen that identity is a column of its own, and the brand is its subject rather than a
 * header pinned to the top of it: the mark sits above the wordmark at display scale, centred in
 * the column, and the empty field that used to surround a small lockup in the top corner is
 * gone. It used to list the three learning spaces and the shared tools; that was a feature list
 * on a page whose one task is signing in, so it is gone rather than replaced with other copy.
 *
 * On a phone the two collapse into one column and the identity reduces to a single compact row,
 * because the form is the whole task there and a tall brand block would only push it down.
 */
export function AuthLayout({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-page-background lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="bg-lab-ink px-5 py-6 text-lab-paper sm:px-10 sm:py-8 lg:flex lg:flex-col lg:px-16 lg:py-14">
        <div className="mx-auto w-full max-w-md lg:mx-0 lg:flex lg:flex-1 lg:flex-col">
          {/*
            The mark is identity here, not navigation: every other route is behind the guard, so a
            link home would only bounce a signed-out visitor back to this screen. The name is real
            text rather than part of the image, so it stays selectable, translatable and legible to
            a screen reader; the icon itself is therefore decorative.

            `lg:my-auto` is what turns the column into a brand plate: the free space splits above
            and below the lockup, so the mark lands in the optical centre and the copyright falls
            to the foot, instead of both crowding the top third.
          */}
          <div className="flex w-fit items-center gap-3 lg:my-auto lg:flex-col lg:items-start lg:gap-12">
            <img
              src="/brand/zhixue-v2/04_智学平台_图标标识_Icon_Only_transparent.png"
              alt=""
              className="size-9 object-contain lg:size-44"
            />
            <span className="flex flex-col">
              <span className="text-card-title font-semibold lg:text-display lg:leading-[0.95]">
                智学平台
              </span>
              <span
                aria-hidden="true"
                className="hidden text-metadata tracking-eyebrow text-lab-grid-light lg:mt-5 lg:block lg:text-body"
              >
                ZHIXUE LEARNING LAB
              </span>
            </span>
          </div>

          <p className="mt-auto hidden pt-12 text-metadata text-lab-grid-light lg:block">
            © 2026 ZHIXUE LEARNING LAB
          </p>
        </div>
      </aside>

      <div className="flex flex-col px-5 py-10 sm:px-10 sm:py-14 lg:px-16 lg:py-16">
        <main className="mx-auto w-full max-w-md flex-1">
          <h1 className="text-page-title font-semibold text-text-primary">{title}</h1>
          {description ? (
            <p className="mt-3 max-w-prose text-body text-text-secondary">{description}</p>
          ) : null}
          <div className="mt-8">{children}</div>
        </main>
        {/* Outside `main`, so it is the page's contentinfo landmark rather than a scoped footer —
            the same thing every other page's footer is. */}
        <footer className="mx-auto mt-10 w-full max-w-md border-t border-border-default pt-5 text-body text-text-secondary">
          {footer}
          <p className="mt-4 text-metadata">
            <Link
              to="/terms"
              className="text-text-secondary underline underline-offset-2 hover:text-text-primary"
            >
              用户协议
            </Link>
            <span aria-hidden="true" className="mx-2 text-text-muted">
              ·
            </span>
            <Link
              to="/privacy"
              className="text-text-secondary underline underline-offset-2 hover:text-text-primary"
            >
              隐私政策
            </Link>
          </p>
        </footer>
      </div>
    </div>
  );
}

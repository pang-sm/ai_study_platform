import type { ReactNode } from 'react';
import { Link } from '@tanstack/react-router';

/**
 * The frame shared by the two published legal documents.
 *
 * These are reading pages, not product screens. They have to be readable while signed out —
 * someone must be able to read the terms before deciding to register — so they carry the mark
 * and one way back into the product instead of the application shell, and they are set at the
 * reading measure rather than the application's. There is no dialog and no accept gate: the
 * documents are here to be read, and the act of registering is what agrees to them.
 */
export function LegalDocument({
  title,
  version,
  updatedAt,
  summary,
  children,
}: {
  title: string;
  version: string;
  updatedAt: string;
  summary: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-page-background text-text-primary">
      <header className="sticky top-0 z-20 border-b border-lab-grid/60 bg-lab-ink text-lab-paper">
        <div className="mx-auto flex h-16 w-full max-w-reading items-center px-5 sm:px-8">
          {/* The one way back: `/` resolves to the product for a signed-in reader and to the
              sign-in screen for a signed-out one, so this link is honest in both states. It also
              names its own colour: the global `a` rule paints links primary blue, which is 3.44:1
              on the ink. */}
          <Link
            to="/"
            aria-label="智学平台首页"
            className="inline-flex items-center gap-2.5 rounded-control text-lab-paper hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent"
          >
            <img
              src="/brand/zhixue-v2/04_智学平台_图标标识_Icon_Only_transparent.png"
              alt=""
              className="size-8 object-contain"
            />
            <span className="text-card-title font-semibold">智学平台</span>
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-reading px-5 py-10 sm:px-8 lg:py-14">
        <h1 className="text-page-title font-semibold">{title}</h1>
        <p className="mt-3 text-metadata text-text-muted">
          {version} · 更新日期 {updatedAt}
        </p>
        <p className="mt-6 text-body text-text-secondary">{summary}</p>
        <div className="mt-10 space-y-10">{children}</div>
      </main>

      <footer className="border-t border-border-default">
        <div className="mx-auto flex w-full max-w-reading flex-wrap items-center gap-x-6 gap-y-2 px-5 py-6 text-body sm:px-8">
          <Link
            to="/terms"
            className="text-text-secondary underline underline-offset-2 hover:text-text-primary"
          >
            用户协议
          </Link>
          <Link
            to="/privacy"
            className="text-text-secondary underline underline-offset-2 hover:text-text-primary"
          >
            隐私政策
          </Link>
          <p className="ml-auto text-metadata text-text-muted">© 2026 ZHIXUE LEARNING LAB</p>
        </div>
      </footer>
    </div>
  );
}

/** One numbered clause. The documents are numbered so a clause can be referred to by number. */
export function LegalSection({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="text-heading font-semibold">
        {n}. {title}
      </h2>
      <div className="mt-3 space-y-3 text-body leading-relaxed text-text-secondary">{children}</div>
    </section>
  );
}

export function LegalList({ items }: { items: readonly ReactNode[] }) {
  return (
    <ul className="list-disc space-y-2 pl-5">
      {items.map((item, index) => (
        // The list is a fixed literal per document, so the index is a stable identity here.
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

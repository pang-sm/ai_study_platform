import type { ReactNode } from 'react';
import { BookOpen } from 'lucide-react';

/**
 * Minimal app shell — exists only to verify mount, router, tokens, icon and font.
 * This is NOT a product home page and should be easy to remove later.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-page-background text-text-primary">
      <header className="border-b border-border-default bg-surface">
        <div className="mx-auto flex h-14 w-full max-w-content items-center gap-2 px-6 lg:px-12">
          <BookOpen className="size-5 text-primary" aria-hidden="true" />
          <span className="font-medium">智学平台</span>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}

import type { ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { Menu, Search } from 'lucide-react';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen overflow-x-hidden bg-page-background text-text-primary">
      <header className="border-b border-lab-grid/60 bg-lab-ink text-lab-paper">
        <div className="mx-auto flex h-16 w-full max-w-content items-center px-5 sm:px-8 lg:px-12">
          <Link to="/" className="shrink-0" aria-label="智学平台首页">
            <img src="/brand/zhixue-v2/08_智学平台_反白标识_Reversed_Dark.png" alt="智学平台" className="hidden h-10 w-auto sm:block" />
            <img src="/brand/zhixue-v2/04_智学平台_图标标识_Icon_Only_transparent.png" alt="智学平台" className="size-9 object-contain sm:hidden" />
          </Link>
          <nav className="ml-10 hidden items-center gap-7 text-body !text-lab-paper-muted md:flex" aria-label="主导航">
            <Link to="/" className="font-medium !text-lab-paper" activeProps={{ 'aria-current': 'page' }}>首页</Link>
            <a href="#learning-worlds" className="!text-lab-paper-muted transition-colors hover:!text-lab-paper">探索学习</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button type="button" aria-label="搜索学习内容" className="inline-flex size-11 items-center justify-center rounded-full text-lab-paper transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent">
              <Search className="size-5" aria-hidden="true" />
            </button>
            <button type="button" aria-label="打开账户菜单" className="hidden size-10 items-center justify-center rounded-full bg-lab-accent text-metadata font-semibold text-lab-ink sm:inline-flex focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent">同</button>
            <button type="button" aria-label="打开导航菜单" className="inline-flex size-11 items-center justify-center rounded-full text-lab-paper transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent md:hidden">
              <Menu className="size-5" aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}

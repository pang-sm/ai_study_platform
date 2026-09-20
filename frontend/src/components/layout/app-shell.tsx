import type { ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { Menu, Search } from 'lucide-react';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen overflow-x-hidden bg-page-background text-text-primary">
      <header className="border-b border-lab-grid/60 bg-lab-ink text-lab-paper">
        <div className="mx-auto flex h-16 w-full max-w-content items-center px-5 sm:px-8 lg:mx-0 lg:h-[76px] lg:max-w-none lg:px-6">
          <Link to="/" className="inline-flex shrink-0 items-center" aria-label="智学平台首页">
            <img src="/brand/zhixue-v2/08_智学平台_Desktop_Header_Lockup.png" alt="智学平台" className="hidden h-[42px] w-auto object-contain sm:block lg:h-[54px]" />
            <img src="/brand/zhixue-v2/04_智学平台_图标标识_Icon_Only_transparent.png" alt="智学平台" className="size-9 object-contain sm:hidden" />
          </Link>
          <div className="ml-4 hidden border-l border-lab-paper/35 pl-4 text-[10px] leading-[1.35] tracking-[0.08em] text-lab-paper-muted lg:block" aria-label="品牌宣言">
            <span className="block">更好的学习</span><span className="block">从这里开始</span>
          </div>
          <nav className="ml-8 hidden items-center gap-7 text-body !text-lab-paper-muted md:flex lg:ml-10" aria-label="主导航">
            <Link to="/exam" className="!text-lab-paper-muted transition-colors hover:!text-lab-paper" activeProps={{ 'aria-current': 'page' }}>考研学习</Link>
            <Link to="/" className="font-medium !text-lab-paper" activeProps={{ 'aria-current': 'page' }}>首页</Link>
            {/* The canonical membership route. It exists because paid features are gated:
                a locked surface needs a real destination, not a dead end. */}
            <Link to="/membership" className="!text-lab-paper-muted transition-colors hover:!text-lab-paper" activeProps={{ 'aria-current': 'page' }}>会员</Link>
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

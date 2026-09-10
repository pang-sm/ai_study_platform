import { Link } from '@tanstack/react-router';

export function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-page-background px-6 text-center">
      <h1 className="text-section-title font-semibold text-text-primary">页面不存在</h1>
      <p className="text-body text-text-secondary">你访问的地址不存在或已被移动。</p>
      <Link to="/" className="text-primary hover:text-primary-hover">
        返回首页
      </Link>
    </div>
  );
}

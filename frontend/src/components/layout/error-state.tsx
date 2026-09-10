export function ErrorState() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-page-background px-6 text-center">
      <h1 className="text-section-title font-semibold text-text-primary">出错了</h1>
      <p className="text-body text-text-secondary">页面加载时发生错误，请稍后重试。</p>
    </div>
  );
}

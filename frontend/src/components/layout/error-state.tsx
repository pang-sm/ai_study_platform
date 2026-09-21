import { useRouter } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';

/**
 * A failed session read is usually transient, and a dead end is the wrong answer to it: the
 * visitor may be perfectly signed in. Retrying re-runs the guards that failed.
 */
export function ErrorState() {
  const router = useRouter();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-page-background px-6 text-center">
      <h1 className="text-section-title font-semibold text-text-primary">出错了</h1>
      <p className="text-body text-text-secondary">
        页面加载时发生错误。如果网络刚刚中断，可以重试。
      </p>
      <Button variant="secondary" onClick={() => void router.invalidate()}>
        重试
      </Button>
    </div>
  );
}

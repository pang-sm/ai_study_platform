import { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate } from '@tanstack/react-router';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { PasswordField } from '@/components/ui/password-field';
import { StatusNote } from '@/components/ui/status-note';
import { TextField } from '@/components/ui/text-field';
import { serverMessage } from '@/lib/api/server-message';
import { cn } from '@/lib/utils';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { useAuth } from '../auth-context';
import { useEmailLogin, useLogin, useSendLoginCode } from '../api/auth';
import { resolvePostAuthDestination } from '../return-to';
import { AuthLayout } from './auth-layout';

const loginSchema = z.object({
  username: z.string().trim().min(1, '请输入账号或邮箱'),
  password: z.string().min(1, '请输入密码'),
});

/**
 * The code step's own validator. It is deliberately a separate schema from the register page's:
 * the two screens ask for the same two strings for different reasons, and sharing one object
 * would mean a message written for one flow appearing in the other.
 */
const emailLoginSchema = z.object({
  email: z.string().trim().min(1, '请输入邮箱地址'),
  code: z.string().trim().min(1, '请输入邮箱验证码'),
});

type LoginValues = z.infer<typeof loginSchema>;
type EmailLoginValues = z.infer<typeof emailLoginSchema>;

type LoginMode = 'password' | 'email-code';

const PANEL_IDS: Record<LoginMode, string> = {
  password: 'login-panel-password',
  'email-code': 'login-panel-email-code',
};

const MODES: readonly { id: LoginMode; label: string }[] = [
  { id: 'password', label: '密码登录' },
  { id: 'email-code', label: '邮箱验证码登录' },
];

function messageOf(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return serverMessage(error.detail) ?? fallback;
  return '网络连接异常，请检查网络后重试。';
}

/**
 * The two ways in, as tabs.
 *
 * Arrow keys move between them and only the selected tab is in the tab order, which is what the
 * tab pattern requires; each tab points at its own panel through `aria-controls`, so the panel
 * that is on screen is the one the selected tab names. Password sign-in is the first tab because
 * it is the way in for everyone; the emailed code needs a verified address and a deployment with
 * mail configured, so it is offered as the alternative rather than as the default.
 */
function ModeTabs({
  mode,
  onSelect,
}: {
  mode: LoginMode;
  onSelect: (mode: LoginMode) => void;
}) {
  const refs = useRef<Record<LoginMode, HTMLButtonElement | null>>({
    password: null,
    'email-code': null,
  });

  const move = (delta: number) => {
    const index = MODES.findIndex((entry) => entry.id === mode);
    const next = MODES[(index + delta + MODES.length) % MODES.length];
    if (!next) return;
    onSelect(next.id);
    refs.current[next.id]?.focus();
  };

  return (
    <div role="tablist" aria-label="登录方式" className="flex gap-1 border-b border-border-default">
      {MODES.map((entry) => {
        const active = entry.id === mode;
        return (
          <button
            key={entry.id}
            ref={(node) => {
              refs.current[entry.id] = node;
            }}
            type="button"
            role="tab"
            id={`login-tab-${entry.id}`}
            aria-selected={active}
            aria-controls={PANEL_IDS[entry.id]}
            tabIndex={active ? 0 : -1}
            onClick={() => onSelect(entry.id)}
            onKeyDown={(event) => {
              if (event.key === 'ArrowRight') {
                event.preventDefault();
                move(1);
              } else if (event.key === 'ArrowLeft') {
                event.preventDefault();
                move(-1);
              }
            }}
            className={cn(
              '-mb-px inline-flex min-h-11 items-center border-b-2 px-3 text-body transition-colors duration-fast ease-standard',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset',
              active
                ? 'border-primary font-medium text-primary-ink'
                : 'border-transparent text-text-secondary hover:text-text-primary',
            )}
          >
            {entry.label}
          </button>
        );
      })}
    </div>
  );
}

function PasswordLoginForm({ destination }: { destination: string }) {
  const navigate = useNavigate();
  const login = useLogin();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: '', password: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login.mutateAsync(values);
      await navigate({ href: destination });
    } catch (error) {
      // The backend already distinguishes the cases it is willing to reveal; showing its own
      // sentence keeps this screen from writing a second, weaker explanation.
      setFormError(messageOf(error, '登录未成功，请稍后重试。'));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <TextField
        label="账号或邮箱"
        type="text"
        autoComplete="username"
        error={errors.username?.message}
        {...register('username')}
      />
      <PasswordField
        label="密码"
        autoComplete="current-password"
        error={errors.password?.message}
        {...register('password')}
      />

      {formError ? <StatusNote tone="danger">{formError}</StatusNote> : null}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? '正在登录…' : '登录'}
      </Button>
    </form>
  );
}

/**
 * Sign-in with a code mailed to an address that is already verified on an account.
 *
 * The send and the verify each keep their own message, and neither is written into a state the
 * other reads: a delivery failure and a wrong code are different problems with different fixes,
 * and a single error slot would let one overwrite the other mid-flow. Nothing here creates an
 * account — the register screen is the only place that does.
 */
function EmailCodeLoginForm({ destination }: { destination: string }) {
  const navigate = useNavigate();
  const sendCode = useSendLoginCode();
  const emailLogin = useEmailLogin();
  const [notice, setNotice] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    getValues,
    trigger,
    formState: { errors },
  } = useForm<EmailLoginValues>({
    resolver: zodResolver(emailLoginSchema),
    defaultValues: { email: '', code: '' },
  });

  const onSend = async () => {
    setSendError(null);
    setNotice(null);
    if (!(await trigger('email'))) return;
    try {
      await sendCode.mutateAsync({ email: getValues('email').trim() });
      setNotice('验证码已发送，请查收邮箱。');
    } catch (error) {
      setSendError(messageOf(error, '验证码发送失败，请稍后重试。'));
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await emailLogin.mutateAsync({ email: values.email.trim(), code: values.code.trim() });
      await navigate({ href: destination });
    } catch (error) {
      setSubmitError(messageOf(error, '登录未成功，请稍后重试。'));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <TextField
        label="邮箱"
        type="email"
        autoComplete="email"
        hint="验证码会发送到已在这台账号上验证过的邮箱。"
        error={errors.email?.message}
        {...register('email')}
      />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Button
          type="button"
          variant="secondary"
          onClick={onSend}
          disabled={sendCode.isPending}
          className="shrink-0"
        >
          {sendCode.isPending ? '正在发送…' : '发送验证码'}
        </Button>
        <p className="text-metadata text-text-muted">没收到可以重新发送。</p>
      </div>

      <TextField
        label="邮箱验证码"
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        error={errors.code?.message}
        {...register('code')}
      />

      {notice ? <StatusNote tone="success">{notice}</StatusNote> : null}
      {sendError ? <StatusNote tone="danger">{sendError}</StatusNote> : null}
      {submitError ? <StatusNote tone="danger">{submitError}</StatusNote> : null}

      <Button type="submit" size="lg" className="w-full" disabled={emailLogin.isPending}>
        {emailLogin.isPending ? '正在登录…' : '登录'}
      </Button>
    </form>
  );
}

export function LoginPage({ returnTo }: { returnTo?: string }) {
  const auth = useAuth();
  const [mode, setMode] = useState<LoginMode>('password');
  const destination = resolvePostAuthDestination(returnTo);

  // The guard reads the cached session so this screen can paint without waiting. When the
  // background read then proves a session already exists, the visitor is moved on instead of
  // being asked to sign in again.
  const navigate = useNavigate();
  useEffect(() => {
    if (auth.isAuthenticated) void navigate({ href: destination });
  }, [auth.isAuthenticated, destination, navigate]);

  if (auth.isAuthenticated) {
    return (
      <AuthLayout
        title="正在进入"
        description="已检测到登录状态，正在打开你的学习页面。"
        footer={<p>如果页面没有自动跳转，请返回首页。</p>}
      >
        <StatusNote>正在进入…</StatusNote>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="登录"
      description="登录后继续你的学习进度、练习记录与复习安排。"
      footer={
        <p>
          还没有账号？{' '}
          <Link to="/register" className="text-primary-ink underline hover:text-primary-hover">
            注册
          </Link>
        </p>
      }
    >
      <div className="space-y-6">
        <ModeTabs mode={mode} onSelect={setMode} />
        <div
          id={PANEL_IDS[mode]}
          role="tabpanel"
          aria-labelledby={`login-tab-${mode}`}
          tabIndex={0}
          className="focus-visible:outline-none"
        >
          {mode === 'password' ? (
            <PasswordLoginForm destination={destination} />
          ) : (
            <EmailCodeLoginForm destination={destination} />
          )}
        </div>
      </div>
    </AuthLayout>
  );
}

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate } from '@tanstack/react-router';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { PasswordField } from '@/components/ui/password-field';
import { StatusNote } from '@/components/ui/status-note';
import { TextField } from '@/components/ui/text-field';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { useRegister, useSendRegisterCode, useVerifyRegisterCode } from '../api/auth';
import { resolvePostAuthDestination } from '../return-to';
import { AuthLayout } from './auth-layout';

/**
 * Mirrors the backend's own check (`"@" in email and "." in the domain part`) rather than
 * applying a stricter rule of its own: a stricter client would refuse addresses the server
 * would have accepted.
 */
const emailSchema = z
  .string()
  .trim()
  .min(1, '请输入邮箱地址')
  .refine((value) => value.includes('@') && value.split('@').pop()?.includes('.'), {
    message: '请输入有效的邮箱地址',
  });

const codeSchema = z.object({
  email: emailSchema,
  code: z.string().trim().min(1, '请输入邮箱验证码'),
});

/**
 * The confirmation is checked here rather than only at the server, because the server has no
 * second field to compare against: `UserCreate` carries one password. A typo in a password that
 * is never echoed back is an account the learner cannot open, so it is caught while they can
 * still see what they typed.
 */
const accountSchema = z
  .object({
    username: z.string().trim().min(1, '请输入账号'),
    password: z.string().min(6, '密码至少需要 6 位'),
    confirmPassword: z.string().min(1, '请再次输入密码'),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ['confirmPassword'],
    message: '两次输入的密码不一致',
  });

function messageOf(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return serverMessage(error.detail) ?? fallback;
  return '网络连接异常，请检查网络后重试。';
}

/**
 * The two halves of registration are two different jobs — proving an address, then naming an
 * account — so they are numbered rather than presented as one long form. A visitor can then see
 * that the second half exists and is not asking for anything yet.
 */
function StepIndicator({ current }: { current: 1 | 2 }) {
  const steps = [
    { index: 1, label: '验证邮箱' },
    { index: 2, label: '设置账号' },
  ] as const;
  return (
    <ol aria-label="注册步骤" className="flex flex-wrap items-center gap-x-6 gap-y-2">
      {steps.map((step) => {
        const active = step.index === current;
        return (
          <li
            key={step.index}
            aria-current={active ? 'step' : undefined}
            className="flex items-center gap-2"
          >
            <span
              aria-hidden="true"
              className={
                active
                  ? 'inline-flex size-6 items-center justify-center rounded-pill bg-primary text-metadata font-semibold text-white'
                  : 'inline-flex size-6 items-center justify-center rounded-pill bg-neutral-soft text-metadata font-semibold text-text-secondary'
              }
            >
              {step.index}
            </span>
            <span
              className={
                active ? 'text-body font-medium text-text-primary' : 'text-body text-text-muted'
              }
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function EmailStep({ onVerified }: { onVerified: (email: string) => void }) {
  const sendCode = useSendRegisterCode();
  const verifyCode = useVerifyRegisterCode();
  const [notice, setNotice] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    getValues,
    trigger,
    formState: { errors },
  } = useForm<z.infer<typeof codeSchema>>({
    resolver: zodResolver(codeSchema),
    defaultValues: { email: '', code: '' },
  });

  const onSend = async () => {
    setErrorText(null);
    setNotice(null);
    if (!(await trigger('email'))) return;
    try {
      await sendCode.mutateAsync({ email: getValues('email').trim() });
      setNotice('验证码已发送，请查收邮箱。');
    } catch (error) {
      setErrorText(messageOf(error, '验证码发送失败，请稍后重试。'));
    }
  };

  const onVerify = handleSubmit(async (values) => {
    setErrorText(null);
    try {
      await verifyCode.mutateAsync({ email: values.email.trim(), code: values.code.trim() });
      onVerified(values.email.trim());
    } catch (error) {
      setErrorText(messageOf(error, '邮箱验证失败，请稍后重试。'));
    }
  });

  return (
    <form onSubmit={onVerify} noValidate className="space-y-6">
      <StepIndicator current={1} />

      <TextField
        label="邮箱"
        type="email"
        autoComplete="email"
        hint="注册需要先验证邮箱；验证完成后才能创建账号。"
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
        <p className="text-metadata text-text-muted">发送到上面填写的邮箱；没收到可以重新发送。</p>
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
      {errorText ? <StatusNote tone="danger">{errorText}</StatusNote> : null}

      <Button type="submit" size="lg" className="w-full" disabled={verifyCode.isPending}>
        {verifyCode.isPending ? '正在验证…' : '验证邮箱'}
      </Button>
    </form>
  );
}

function AccountStep({ email, destination }: { email: string; destination: string }) {
  const navigate = useNavigate();
  const registerUser = useRegister();
  const [errorText, setErrorText] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof accountSchema>>({
    resolver: zodResolver(accountSchema),
    defaultValues: { username: '', password: '', confirmPassword: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setErrorText(null);
    try {
      // `email` is the address proven in the previous step; the backend re-checks the proof
      // cookie, so this cannot create an account for an unverified address. `confirmPassword`
      // is this form's own check and is not part of the request body.
      await registerUser.mutateAsync({
        username: values.username.trim(),
        password: values.password,
        email,
      });
      await navigate({ href: destination });
    } catch (error) {
      setErrorText(messageOf(error, '注册未成功，请稍后重试。'));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      <StepIndicator current={2} />

      <StatusNote tone="success">邮箱 {email} 已验证。</StatusNote>

      <TextField
        label="账号"
        type="text"
        autoComplete="username"
        error={errors.username?.message}
        {...register('username')}
      />
      <PasswordField
        label="密码"
        autoComplete="new-password"
        hint="至少 6 位。"
        error={errors.password?.message}
        {...register('password')}
      />
      <PasswordField
        label="确认密码"
        autoComplete="new-password"
        error={errors.confirmPassword?.message}
        {...register('confirmPassword')}
      />

      {errorText ? <StatusNote tone="danger">{errorText}</StatusNote> : null}

      <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? '正在创建账号…' : '创建账号'}
      </Button>
    </form>
  );
}

export function RegisterPage({ returnTo }: { returnTo?: string }) {
  const [verifiedEmail, setVerifiedEmail] = useState<string | null>(null);
  // A visitor who arrived from a setup screen finishes sign-up and lands back where they were
  // going, not on Home. The destination was validated by the route before it reached here.
  const destination = resolvePostAuthDestination(returnTo);
  const loginSearch = returnTo ? { returnTo } : undefined;

  return (
    <AuthLayout
      title="注册"
      description={
        verifiedEmail
          ? '邮箱已验证。设置账号和密码即可开始。'
          : '注册需要先验证邮箱，验证后即可设置账号密码。'
      }
      footer={
        <p>
          已有账号？{' '}
          <Link
            to="/login"
            search={loginSearch}
            className="text-primary-ink underline hover:text-primary-hover"
          >
            登录
          </Link>
        </p>
      }
    >
      {verifiedEmail ? (
        <AccountStep email={verifiedEmail} destination={destination} />
      ) : (
        <EmailStep onVerified={setVerifiedEmail} />
      )}
    </AuthLayout>
  );
}

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { TextField } from '@/components/ui/text-field';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import type { UserProfile } from '@/features/auth/api/user-profile';
import { useChangePassword, useSendEmailCode, useVerifyEmail, useSendPhoneCode, useVerifyPhone } from '../api/profile';

function messageOf(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return serverMessage(error.detail) ?? fallback;
  return '网络连接异常，请检查网络后重试。';
}

/**
 * Mirrors the backend's rules exactly: every field present, the new password at least 8
 * characters (the register screen's floor is 6 — these are two different checks and the stricter
 * one wins here), the confirmation identical, and the new password different from the old.
 */
const passwordSchema = z
  .object({
    old_password: z.string().min(1, '请输入当前密码'),
    new_password: z.string().min(8, '新密码长度至少 8 位'),
    confirm_password: z.string().min(1, '请再次输入新密码'),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ['confirm_password'],
    message: '两次输入的新密码不一致',
  })
  .refine((values) => values.new_password !== values.old_password, {
    path: ['new_password'],
    message: '新密码不能与旧密码相同',
  });

export function PasswordForm() {
  const changePassword = useChangePassword();
  const [errorText, setErrorText] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { old_password: '', new_password: '', confirm_password: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setErrorText(null);
    try {
      await changePassword.mutateAsync(values);
      reset();
    } catch (error) {
      setErrorText(messageOf(error, '密码修改未成功，请稍后重试。'));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <TextField
        label="当前密码"
        type="password"
        autoComplete="current-password"
        error={errors.old_password?.message}
        {...register('old_password')}
      />
      <TextField
        label="新密码"
        type="password"
        autoComplete="new-password"
        hint="至少 8 位。"
        error={errors.new_password?.message}
        {...register('new_password')}
      />
      <TextField
        label="确认新密码"
        type="password"
        autoComplete="new-password"
        error={errors.confirm_password?.message}
        {...register('confirm_password')}
      />
      <div className="flex flex-wrap items-center gap-4">
        <Button type="submit" disabled={changePassword.isPending}>
          {changePassword.isPending ? '正在修改…' : '修改密码'}
        </Button>
        {changePassword.isSuccess ? (
          <p role="status" className="text-body text-success-ink">
            密码已修改。
          </p>
        ) : null}
        {errorText ? (
          <p role="alert" className="text-body text-danger-ink">
            {errorText}
          </p>
        ) : null}
      </div>
    </form>
  );
}

export function EmailSection({ profile }: { profile: UserProfile }) {
  const sendCode = useSendEmailCode();
  const verify = useVerifyEmail();
  const [errorText, setErrorText] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    getValues,
    trigger,
    formState: { errors },
  } = useForm<{ email: string; code: string }>({
    resolver: zodResolver(
      z.object({ email: z.string().trim().min(1, '请输入邮箱地址'), code: z.string().trim() }),
    ),
    defaultValues: { email: '', code: '' },
  });

  // Email is bind-once: `PUT /me/email/verify` refuses an account that already has one
  // (`EMAIL_ALREADY_BOUND`), so a bound address is shown rather than offered for editing.
  if (profile.email_verified && profile.email) {
    return (
      <div className="space-y-2">
        <p className="text-body text-text-primary">已绑定邮箱：{profile.email}</p>
        <p className="text-metadata text-text-muted">当前版本不支持更换已绑定的邮箱。</p>
      </div>
    );
  }

  const onSend = async () => {
    setErrorText(null);
    setNotice(null);
    if (!(await trigger('email'))) return;
    try {
      await sendCode.mutateAsync(getValues('email').trim());
      setNotice('验证码已发送，请查收邮箱。');
    } catch (error) {
      setErrorText(messageOf(error, '验证码发送失败，请稍后重试。'));
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    setErrorText(null);
    try {
      await verify.mutateAsync({ email: values.email.trim(), code: values.code.trim() });
    } catch (error) {
      setErrorText(messageOf(error, '邮箱绑定失败，请稍后重试。'));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <TextField label="邮箱" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
      <div>
        <Button type="button" variant="secondary" onClick={onSend} disabled={sendCode.isPending}>
          {sendCode.isPending ? '正在发送…' : '发送验证码'}
        </Button>
      </div>
      <TextField
        label="邮箱验证码"
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        error={errors.code?.message}
        {...register('code')}
      />
      {notice ? (
        <p role="status" className="text-body text-success-ink">
          {notice}
        </p>
      ) : null}
      {errorText ? (
        <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-body text-danger-ink">
          {errorText}
        </p>
      ) : null}
      <Button type="submit" disabled={verify.isPending}>
        {verify.isPending ? '正在绑定…' : '绑定邮箱'}
      </Button>
    </form>
  );
}

export function PhoneSection({ profile }: { profile: UserProfile }) {
  const bound = Boolean(profile.phone_verified && profile.phone);
  // `bind` and `change` are different backend routes: bind refuses an account that already has a
  // verified number, change is the one that replaces it.
  const flow = bound ? 'change' : 'bind';
  const sendCode = useSendPhoneCode();
  const verify = useVerifyPhone();
  const [errorText, setErrorText] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    getValues,
    trigger,
    formState: { errors },
  } = useForm<{ phone: string; code: string }>({
    resolver: zodResolver(
      z.object({
        phone: z.string().trim().min(1, '请输入手机号'),
        code: z.string().trim().min(1, '请输入短信验证码'),
      }),
    ),
    defaultValues: { phone: '', code: '' },
  });

  const onSend = async () => {
    setErrorText(null);
    setNotice(null);
    if (!(await trigger('phone'))) return;
    try {
      await sendCode.mutateAsync({ phone: getValues('phone').trim(), flow });
      setNotice('验证码已发送，请查收短信。');
    } catch (error) {
      setErrorText(messageOf(error, '验证码发送失败，请稍后重试。'));
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    setErrorText(null);
    try {
      await verify.mutateAsync({ phone: values.phone.trim(), code: values.code.trim(), flow });
    } catch (error) {
      setErrorText(messageOf(error, '手机号验证失败，请稍后重试。'));
    }
  });

  return (
    <div className="space-y-5">
      {bound ? (
        <p className="text-body text-text-primary">已绑定手机号：{profile.phone}</p>
      ) : (
        <p className="text-body text-text-secondary">尚未绑定手机号。</p>
      )}
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        <TextField
          label={bound ? '新手机号' : '手机号'}
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          hint="中国大陆手机号。"
          error={errors.phone?.message}
          {...register('phone')}
        />
        <div>
          <Button type="button" variant="secondary" onClick={onSend} disabled={sendCode.isPending}>
            {sendCode.isPending ? '正在发送…' : '发送验证码'}
          </Button>
        </div>
        <TextField
          label="短信验证码"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          error={errors.code?.message}
          {...register('code')}
        />
        {notice ? (
          <p role="status" className="text-body text-success-ink">
            {notice}
          </p>
        ) : null}
        {errorText ? (
          <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-body text-danger-ink">
            {errorText}
          </p>
        ) : null}
        <Button type="submit" disabled={verify.isPending}>
          {verify.isPending ? '正在验证…' : bound ? '更换手机号' : '绑定手机号'}
        </Button>
      </form>
    </div>
  );
}

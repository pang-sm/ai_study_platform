import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { SaveRow } from '@/components/ui/save-row';
import { TextField } from '@/components/ui/text-field';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import type { UserProfile } from '@/features/auth/api/user-profile';
import { useUpdateProfile } from '../api/profile';

/** Mirrors the backend's own allow-lists so the form cannot offer a value the server rejects. */
const GRADES = ['大一', '大二', '大三', '大四', '研究生'] as const;
const SEMESTERS = ['上学期', '下学期'] as const;

const personalSchema = z.object({
  nickname: z.string().trim().max(30, '昵称最多 30 个字符'),
  grade: z.string(),
  major: z.string().trim().max(50, '专业最多 50 个字符'),
  semester: z.string(),
});

const learningSchema = z.object({
  learning_direction: z.string().trim().max(100, '学习方向最多 100 个字符'),
});

type PersonalValues = z.infer<typeof personalSchema>;
type LearningValues = z.infer<typeof learningSchema>;

const controlClasses =
  'mt-2 h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

export function PersonalInfoForm({ profile }: { profile: UserProfile }) {
  const update = useUpdateProfile();
  const [errorText, setErrorText] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<PersonalValues>({
    resolver: zodResolver(personalSchema),
    defaultValues: {
      nickname: profile.nickname ?? '',
      grade: profile.grade ?? '',
      major: profile.major ?? '',
      semester: profile.semester ?? '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setErrorText(null);
    try {
      await update.mutateAsync(values);
    } catch (error) {
      setErrorText(
        error instanceof ApiRequestError
          ? (serverMessage(error.detail) ?? '保存未成功，请稍后重试。')
          : '网络连接异常，请检查网络后重试。',
      );
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <TextField label="昵称" type="text" error={errors.nickname?.message} {...register('nickname')} />
      <div>
        <label htmlFor="profile-grade" className="block text-body font-medium text-text-primary">
          年级
        </label>
        <select id="profile-grade" className={controlClasses} {...register('grade')}>
          <option value="">未填写</option>
          {GRADES.map((grade) => (
            <option key={grade} value={grade}>
              {grade}
            </option>
          ))}
        </select>
      </div>
      <TextField label="专业" type="text" error={errors.major?.message} {...register('major')} />
      <div>
        <label htmlFor="profile-semester" className="block text-body font-medium text-text-primary">
          学期
        </label>
        <select id="profile-semester" className={controlClasses} {...register('semester')}>
          <option value="">未填写</option>
          {SEMESTERS.map((semester) => (
            <option key={semester} value={semester}>
              {semester}
            </option>
          ))}
        </select>
      </div>
      <SaveRow isPending={update.isPending} saved={update.isSuccess} error={errorText} />
    </form>
  );
}

/**
 * Only fields with a real consumer are editable here. `ai_answer_style`, `answer_detail_level`,
 * `material_reference_preference`, `learning_stage`, `school` and `daily_study_minutes` are
 * stored and returned by `PUT /me/profile` but read by nothing in the backend, so presenting
 * them as settings would promise an effect that does not exist.
 *
 * `focus_courses` is gone from this form for the opposite reason: it *is* read, as the fallback
 * source of a learner's courses, which made it a second and indirect way to establish the same
 * fact the course setup flow now establishes directly. Two write paths for one fact is how the
 * two drift apart, so the course list is edited where it is owned.
 *
 * The per-subject plan settings (daily hours, weekly days, review strategy) ARE effective, and
 * they belong to the surface that owns them — this section links there instead of duplicating.
 */
export function LearningSettingsForm({ profile }: { profile: UserProfile }) {
  const update = useUpdateProfile();
  const [errorText, setErrorText] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LearningValues>({
    resolver: zodResolver(learningSchema),
    defaultValues: {
      learning_direction: profile.learning_direction ?? '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setErrorText(null);
    try {
      await update.mutateAsync(values);
    } catch (error) {
      setErrorText(
        error instanceof ApiRequestError
          ? (serverMessage(error.detail) ?? '保存未成功，请稍后重试。')
          : '网络连接异常，请检查网络后重试。',
      );
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      <TextField
        label="学习方向"
        type="text"
        hint="例如：计算机考研 408。课程、备考科目与编程语言分别在各自的学习空间里设置。"
        error={errors.learning_direction?.message}
        {...register('learning_direction')}
      />
      <SaveRow isPending={update.isPending} saved={update.isSuccess} error={errorText} />
    </form>
  );
}

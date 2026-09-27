import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SectionHeading } from '@/components/ui/section-heading';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { apiClient } from '@/lib/api/client';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { useUpdateProfile } from '@/features/profile/api/profile';
import { buildFramework } from '../course-framework';
import { cn } from '@/lib/utils';

/** The courses the recommendation offers, which is the only part of the answer this section uses. */
function readRecommendation(value: unknown): readonly string[] {
  const row = typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};
  return Array.isArray(row.suggested_courses)
    ? row.suggested_courses.filter((entry): entry is string => typeof entry === 'string')
    : [];
}

/**
 * 学习框架 — the bands a course of study is read in, and the one control that adds to them.
 *
 * WHAT IS SHOWN
 * The bands hold everything the learner currently holds, plus whatever the recommendation offers.
 * A course already declared is therefore still visible here, as part of the framework it belongs
 * to; it is shown by a checked, disabled box rather than by a label saying so.
 *
 * WHY IT SAVES BEFORE IT ASKS
 * The recommendation is computed from the major and grade stored on the account, not from
 * whatever is currently typed in the form — there is no parameter for them. So pressing 生成 sends
 * those two fields first and reads the answer second. Doing it the other way round would answer
 * about the previous major, which is worse than not answering.
 *
 * WHY NOTHING IS ADDED UNTIL IT IS CONFIRMED
 * A recommendation the learner never agreed to would appear in their course list as though they
 * had declared it. Everything here is offered, ticked by default (a recommendation nobody wants is
 * easier to untick than an empty list is to fill), and only written when 加入我的课程 is pressed.
 */
export function CourseFrameworkPanel({
  major,
  grade,
  existing,
  onAdd,
}: {
  major: string;
  grade: string;
  /** The courses already declared, so the panel does not offer to add them twice. */
  existing: readonly string[];
  onAdd: (courses: readonly string[]) => void;
}) {
  const updateProfile = useUpdateProfile();
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const [added, setAdded] = useState(false);

  const generate = useMutation({
    mutationFn: async (): Promise<readonly string[]> => {
      await updateProfile.mutateAsync({ major: major.trim(), grade: grade.trim() });
      const { data, error, response } = await apiClient.GET('/membership/recommendation', {});
      if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
      const courses = readRecommendation(data);
      // Everything not already declared starts ticked. The list is a proposal, and a proposal is
      // read faster when the default is visible than when it has to be assembled one tick at a time.
      setChosen(new Set(courses.filter((name) => !existing.includes(name))));
      setAdded(false);
      return courses;
    },
  });

  const ready = Boolean(major.trim() && grade.trim());
  const recommendation = generate.data;
  // The framework as it stands: what the recommendation offers, in front of what the learner
  // already holds. Both are banded by name, the only identity either carries.
  const framework = [...new Set([...(recommendation ?? []), ...existing])];
  const bands = buildFramework(framework, grade);
  const selectable = bands.flatMap((band) => band.courses).filter((name) => !existing.includes(name));
  const hasChoice = selectable.some((name) => chosen.has(name));

  const toggle = (name: string) => {
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const confirm = () => {
    const names = selectable.filter((name) => chosen.has(name));
    if (!names.length) return;
    onAdd(names);
    setAdded(true);
  };

  return (
    <section aria-labelledby="course-framework-title" className="border-t border-border-default pt-8">
      <SectionHeading id="course-framework-title" title="学习框架" />

      {bands.length ? (
        <div className="mt-6 space-y-6">
          {bands.map((band) => (
            <div key={band.category}>
              <h3 className="text-body font-medium text-text-primary">{band.category}</h3>
              <ul className="mt-3 border-t border-border-default">
                {band.courses.map((name) => {
                  const already = existing.includes(name);
                  const checked = already || chosen.has(name);
                  return (
                    <li key={name} className="border-b border-border-default">
                      <label
                        className={cn(
                          'flex min-h-12 items-center gap-3 py-2',
                          already ? 'text-text-muted' : 'text-text-primary',
                        )}
                      >
                        <input
                          type="checkbox"
                          className="size-4 accent-primary"
                          checked={checked}
                          disabled={already}
                          onChange={() => toggle(name)}
                        />
                        <span>{name}</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      ) : null}

      {!recommendation && !generate.isPending ? (
        <Button
          className="mt-6"
          variant="secondary"
          disabled={!ready}
          onClick={() => generate.mutate()}
        >
          <Sparkles className="size-4" aria-hidden="true" />
          生成推荐学习框架
        </Button>
      ) : null}

      {generate.isPending ? (
        <div className="mt-6 space-y-3" aria-hidden="true">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : null}

      {generate.isError ? (
        <StatusNote tone="danger" className="mt-5">
          {generate.error instanceof ApiRequestError && serverMessage(generate.error.detail)
            ? serverMessage(generate.error.detail)
            : '暂时没能生成推荐，稍后再试或直接手动添加课程。'}
          <button type="button" className="ml-3 underline" onClick={() => generate.mutate()}>
            再试一次
          </button>
        </StatusNote>
      ) : null}

      {recommendation && !bands.length ? (
        <StatusNote className="mt-5">暂时没有可推荐的课程。</StatusNote>
      ) : null}

      {recommendation && bands.length ? (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button onClick={confirm} disabled={added || !hasChoice}>
            加入我的课程
          </Button>
          <button
            type="button"
            className="text-body text-primary-ink underline"
            onClick={() => generate.mutate()}
          >
            重新生成
          </button>
        </div>
      ) : null}

      {added ? (
        <StatusNote tone="success" className="mt-4">
          已加入，保存后生效。
        </StatusNote>
      ) : null}
    </section>
  );
}

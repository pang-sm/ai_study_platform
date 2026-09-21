import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { CheckboxRow, RadioRow } from '@/components/ui/choice-list';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { SaveRow } from '@/components/ui/save-row';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { resolveReturnDestination } from '@/features/auth/return-to';
import { useProgrammingOnboarding, useSaveProgrammingOnboarding } from '../api/programming';
import {
  CANONICAL_LANGUAGES,
  PROGRAMMING_LEVELS,
  PROGRAMMING_PROBLEMS,
  levelLabel,
  readProgrammingOnboarding,
  type ProgrammingOnboardingState,
} from '../programming-onboarding';

/**
 * Where a learner's programming context is established.
 *
 * It asks only for what `POST /programming/onboarding` needs and stores: the languages the
 * runner can execute, the current level, and — optionally — what is currently hard. The stored
 * package (`plan`) is echoed back on save but never offered here: it is a membership fact that
 * the membership surface owns, and a save that silently reset it would move a paid learner to
 * the free plan, so the value the server returned is what goes back.
 *
 * Nothing on this page predicts anything. "当前水平" is what the learner says about themselves;
 * the product does not compute it, and no copy here claims otherwise.
 */
export function ProgrammingSetupPage({ returnTo }: { returnTo?: string }) {
  const onboarding = useProgrammingOnboarding();
  const destination = resolveReturnDestination(returnTo, '/programming/');

  if (onboarding.isPending) {
    return (
      <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
        <LoadingState label="正在读取编程学习设置…" />
      </div>
    );
  }

  if (onboarding.isError) {
    return (
      <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
        <PageHeader eyebrow="编程学习" title="设置编程学习" />
        <StatusNote tone="danger" className="mt-8">
          编程学习设置暂时无法读取，因此这里不能安全地保存。请稍后重试。
        </StatusNote>
      </div>
    );
  }

  return (
    <ProgrammingSetupForm
      initial={readProgrammingOnboarding(onboarding.data)}
      destination={destination}
    />
  );
}

function ProgrammingSetupForm({
  initial,
  destination,
}: {
  initial: ProgrammingOnboardingState;
  destination: string;
}) {
  const navigate = useNavigate();
  const save = useSaveProgrammingOnboarding();
  const [languages, setLanguages] = useState(initial.languages);
  const [level, setLevel] = useState(initial.level);
  const [problems, setProblems] = useState(initial.problems);
  const [errorText, setErrorText] = useState<string | null>(null);

  const toggleLanguage = (language: string, checked: boolean) => {
    setLanguages((current) =>
      checked
        ? [...current, language as (typeof current)[number]]
        : current.filter((value) => value !== language),
    );
  };
  const toggleProblem = (problem: string, checked: boolean) => {
    setProblems((current) =>
      checked ? [...current, problem] : current.filter((value) => value !== problem),
    );
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorText(null);
    try {
      await save.mutateAsync({
        main_language: languages[0] ?? '',
        selected_languages: [...languages],
        level,
        problems,
        plan: initial.plan,
        onboarding_completed: true,
      });
      await navigate({ href: destination });
    } catch (error) {
      setErrorText(
        error instanceof ApiRequestError
          ? (serverMessage(error.detail) ?? '保存未成功，请稍后重试。')
          : '网络连接异常，请检查网络后重试。',
      );
    }
  };

  return (
    <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <PageHeader
        eyebrow="编程学习"
        title={initial.completed ? '编程学习设置' : '设置编程学习'}
        description="练习、运行、提交与记录都挂在具体一门语言下，所以先确定要练的语言和当前水平。"
      />

      {initial.unknownLanguages.length ? (
        <StatusNote tone="warning" className="mt-8">
          当前设置里有平台无法运行的语言：{initial.unknownLanguages.join('、')}。平台只运行 C、C++、Python、Java；
          保存后这个值会被替换为你下面选择的结果。
        </StatusNote>
      ) : null}

      <form onSubmit={onSubmit} noValidate className="mt-8 max-w-2xl space-y-10">
        <fieldset>
          <legend className="text-card-title font-semibold text-text-primary">练习语言</legend>
          <p className="mt-1 max-w-prose text-body text-text-secondary">
            至少选择一种。只有这里列出的语言有可运行的编译或解释环境。
          </p>
          <div className="mt-4 border-t border-border-default">
            {CANONICAL_LANGUAGES.map((language) => (
              <CheckboxRow
                key={language}
                name="languages"
                value={language}
                checked={languages.includes(language)}
                onChange={(checked) => toggleLanguage(language, checked)}
              >
                {language}
              </CheckboxRow>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-card-title font-semibold text-text-primary">当前水平</legend>
          <p className="mt-1 max-w-prose text-body text-text-secondary">
            这是你对自己当前情况的说明，用于确定练习起点；选择具体的语言后随时可以改。
          </p>
          <div className="mt-4 border-t border-border-default">
            {PROGRAMMING_LEVELS.map((item) => (
              <RadioRow
                key={item.key}
                name="level"
                value={item.key}
                checked={level === item.key}
                onChange={(checked) => {
                  if (checked) setLevel(item.key);
                }}
              >
                {item.label}
              </RadioRow>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-card-title font-semibold text-text-primary">现在的主要困难</legend>
          <p className="mt-1 max-w-prose text-body text-text-secondary">
            可以留空。选了之后，它会作为你练习时会遇到的困难记录在设置里。
          </p>
          <div className="mt-4 border-t border-border-default">
            {PROGRAMMING_PROBLEMS.map((item) => (
              <CheckboxRow
                key={item.key}
                name="problems"
                value={item.key}
                checked={problems.includes(item.key)}
                onChange={(checked) => toggleProblem(item.key, checked)}
              >
                {item.label}
              </CheckboxRow>
            ))}
          </div>
        </fieldset>

        {languages.length === 0 ? (
          <StatusNote tone="warning">请至少选择一种练习语言。</StatusNote>
        ) : null}
        {!level ? <StatusNote tone="warning">请选择当前水平。</StatusNote> : null}

        <SaveRow
          label={initial.completed ? '保存设置' : '保存并开始'}
          isPending={save.isPending}
          saved={false}
          error={errorText}
        />
      </form>

      {initial.completed ? (
        <section aria-labelledby="programming-setup-current" className="mt-12 border-t border-border-default pt-8">
          <SectionHeading
            id="programming-setup-current"
            title="当前保存的设置"
            description="这是服务端当前存储的编程学习上下文。"
          />
          <dl className="mt-5 max-w-2xl space-y-3">
            <div>
              <dt className="text-metadata font-medium tracking-eyebrow text-text-muted">练习语言</dt>
              <dd className="mt-1 text-body text-text-primary">
                {initial.languages.length ? initial.languages.join('、') : '未设置'}
              </dd>
            </div>
            <div>
              <dt className="text-metadata font-medium tracking-eyebrow text-text-muted">当前水平</dt>
              <dd className="mt-1 text-body text-text-primary">{levelLabel(initial.level)}</dd>
            </div>
          </dl>
          <Button asChild variant="secondary" className="mt-6">
            <Link to="/programming">进入编程学习</Link>
          </Button>
        </section>
      ) : null}
    </div>
  );
}

import { useMemo, useState, type FormEvent } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { StatusNote } from '@/components/ui/status-note';
import { TextField } from '@/components/ui/text-field';
import { serverMessage } from '@/lib/api/server-message';
import { resolveReturnDestination } from '@/features/auth/return-to';
import { useExamCatalog, type ExamCatalog } from '../api/catalog';
import { ApiRequestError } from '../api/content-status';
import { useExamProfile, useSaveExamProfile, type ExamProfile } from '../api/profile';
import {
  EXAM_PLAN_DISCLAIMER,
  NO_UNIFIED_MATH,
  combinationReplacesSelection,
  examTypeLabel,
  planOptions,
  professionalGroups,
  recommendedSubjects,
  type ExamSubjectOption,
} from '../view-models/exam-plan';
import { ExamPageShell } from './exam-page-shell';

/**
 * 设置考试方案 — the exam space's one configuration surface.
 *
 * It used to be a form: every field the profile has, in catalogue order, with a step rail drawn
 * above it. A learner opening it met six numbered sections before anything explained what the
 * screen was for. It is now the conversation a learner actually has with themselves — which exam
 * and which year, which professional paper, which public courses, and then reading the plan back —
 * and the exam type is stated rather than offered, because exactly one type exists and a control
 * whose only choice is the right one is not a decision.
 *
 * What it does NOT do is decide the combination. `suggested_subjects` is empty in the catalogue for
 * every direction on purpose: which public courses a direction requires varies by institution,
 * degree type and admissions year, and no source in this repository can state it. So the direction
 * offers a starting combination the learner applies explicitly, with the 招生专业目录 disclaimer
 * beside it, and the learner's own confirmation is what the profile stores.
 */
export function ExamSetupPage({ returnTo }: { returnTo?: string }) {
  const catalog = useExamCatalog();
  const profile = useExamProfile();
  const destination = resolveReturnDestination(returnTo, '/exam');

  if (catalog.isPending || profile.isPending) {
    return (
      <ExamPageShell>
        <LoadingState label="正在读取考试方案…" />
      </ExamPageShell>
    );
  }

  if (catalog.isError || profile.isError) {
    return (
      <ExamPageShell>
        <PageHeader title="设置考试方案" />
        <StatusNote tone="danger" className="mt-8">
          考试方案暂时无法读取，因此这里不能安全地保存。请稍后重试。
        </StatusNote>
      </ExamPageShell>
    );
  }

  return <ExamPlanFlow catalog={catalog.data} profile={profile.data} destination={destination} />;
}

/** The three things the learner walks through, in their words rather than the schema's. */
const STEP_TITLES = ['备考方向与专业课', '公共课', '确认考试方案'] as const;
const LAST_STEP = STEP_TITLES.length - 1;

/** The absence of a choice on a single-choice line. See `NO_UNIFIED_MATH` for the maths case. */
const NOT_CHOSEN = '';

function ExamPlanFlow({
  catalog,
  profile,
  destination,
}: {
  catalog: ExamCatalog;
  profile: ExamProfile;
  destination: string;
}) {
  const navigate = useNavigate();
  const save = useSaveExamProfile();
  const options = useMemo(() => planOptions(catalog), [catalog]);
  const groups = useMemo(() => professionalGroups(options), [options]);

  const [step, setStep] = useState(0);
  // A year already on the profile is shown and kept: opening this screen to change a subject must
  // never quietly discard the target the learner set last time.
  const [year, setYear] = useState(profile.target_exam_year?.toString() ?? '');
  const [track, setTrack] = useState(profile.selected_track ?? '');
  const [subjects, setSubjects] = useState<string[]>(profile.selected_subjects);
  // 自命题专业课: names the learner owns. They are NOT catalogue subjects — those are frozen
  // config — so they are kept and sent separately, as their own field.
  const [customNames, setCustomNames] = useState((profile.custom_subjects ?? []).map((item) => item.name));
  const [customDraft, setCustomDraft] = useState('');
  const [pendingCombination, setPendingCombination] = useState<readonly string[] | null>(null);

  const selectedTrack = catalog.tracks.find((item) => item.id === track);
  const politics = subjects.filter((id) => options.politics.some((option) => option.id === id));
  const english = subjects.find((id) => options.english.some((option) => option.id === id)) ?? NOT_CHOSEN;
  const math = subjects.find((id) => options.math.some((option) => option.id === id)) ?? NO_UNIFIED_MATH;
  const professional = subjects.filter((id) => options.professional.some((option) => option.id === id));

  const recommendation = recommendedSubjects(selectedTrack);
  const recommendationLabels = recommendation.map((id) => anyOptionName(options, id));
  // A 自命题 subject is part of the plan even though it is not a catalogue id, so "has the
  // learner chosen anything" has to count it — otherwise a plan holding only one would confirm
  // as empty and hide the very subject the learner just added.
  const hasSelection = Boolean(
    politics.length || english || math || professional.length || customNames.length,
  );

  /** Replace the single choice on one public-course line, leaving every other line untouched. */
  const chooseOne = (line: readonly ExamSubjectOption[], next: string) => {
    const ids = new Set(line.map((option) => option.id));
    setSubjects((current) => [...current.filter((id) => !ids.has(id)), ...(next ? [next] : [])]);
  };

  const toggleIn = (id: string) =>
    setSubjects((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));

  /**
   * Apply a suggested combination.
   *
   * The suggestion only ever lands here, and only ever after this click. When it would drop
   * something the learner had already chosen the click asks first: a button that silently removed
   * a subject they picked would be the product deciding their exam for them.
   */
  const applyCombination = (next: readonly string[]) => {
    if (combinationReplacesSelection(subjects, next)) {
      setPendingCombination(next);
      return;
    }
    setSubjects([...next]);
  };

  const addCustomName = () => {
    const value = customDraft.trim().slice(0, 60);
    if (!value || customNames.includes(value)) return;
    setCustomNames((current) => [...current, value]);
    setCustomDraft('');
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await save.mutateAsync({
      selected_track: track || null,
      selected_subjects: subjects,
      target_exam_year: year ? Number(year) : null,
      custom_subjects: customNames,
    });
    await navigate({ href: destination });
  };

  const saveError = save.isError
    ? save.error instanceof ApiRequestError
      ? (serverMessage(save.error.detail) ?? '保存未成功，请稍后重试。')
      : '网络连接异常，请检查网络后重试。'
    : null;

  // The exam is the headline; the year is part of its name only once the learner has set one, so
  // an unset year reads as the exam rather than as a form field that is missing.
  const yearLabel = year ? `${year} ${examTypeLabel(catalog.exam_type)}` : examTypeLabel(catalog.exam_type);

  return (
    <ExamPageShell>
      <PageHeader title="设置考试方案" description="考试方案决定你在考研学习里的学习范围。" />

      {/* The plan's own top line: which exam, and which year. The year is a property of the whole
          plan, so it is edited here — at the top, where the plan is stated — rather than saved for
          a late "extra field" step, and the one exam type the product supports is stated beside it
          instead of offered as a choice with a single right answer. */}
      <div className="exam-setup__target mt-6">
        <p className="exam-setup__target-kicker">目标考试</p>
        <div className="exam-setup__target-row">
          <input
            id="exam-target-year"
            aria-label="目标考试年份"
            className="exam-setup__year"
            type="number"
            inputMode="numeric"
            placeholder="年份"
            value={year}
            onChange={(event) => setYear(event.target.value)}
          />
          <span className="exam-setup__target-value">{examTypeLabel(catalog.exam_type)}</span>
        </div>
        <p className="exam-setup__target-hint">年份是你的目标年份，不是真题年份；可以留空。</p>
      </div>

      <form onSubmit={submit} noValidate className="exam-setup mt-6">
        <p className="exam-setup__progress">
          第 {step + 1} 步，共 {STEP_TITLES.length} 步 · {STEP_TITLES[step]}
        </p>

        {/* The step is a labelled region, so a screen reader announces which step it is in and
            the title is not repeated as loose text outside the thing it names. */}
        <section className="exam-step" aria-labelledby="exam-step-title">
          <h2 className="exam-step__title" id="exam-step-title">{STEP_TITLES[step]}</h2>
          <p className="exam-step__hint">{STEP_HINTS[step]}</p>

          {step === 0 ? (
            <>
              <fieldset className="exam-step__group">
                <legend className="exam-step__group-title">备考方向</legend>
                <p className="exam-step__hint">
                  用于帮助生成常见考试科目组合，不会自动修改你已经确认的考试科目。
                </p>
                <div className="exam-options">
                  {catalog.tracks.map((item) => (
                    <Option
                      key={item.id}
                      type="radio"
                      name="exam-track"
                      value={item.id}
                      checked={track === item.id}
                      onChange={() => setTrack(item.id)}
                      title={item.display_name}
                      detail={item.description || undefined}
                      meta={item.availability === 'framework_only' ? '内容建设中' : undefined}
                    />
                  ))}
                </div>
                {recommendation.length ? (
                  <div className="exam-recommend">
                    <p className="exam-recommend__title">常见组合</p>
                    <p className="exam-recommend__value">{recommendationLabels.join(' + ')}</p>
                    <div className="exam-recommend__foot">
                      <p className="exam-recommend__note">仅供参考，{EXAM_PLAN_DISCLAIMER}</p>
                      <Button type="button" variant="secondary" onClick={() => applyCombination(recommendation)}>
                        使用此组合
                      </Button>
                    </div>
                  </div>
                ) : null}
              </fieldset>

              <fieldset className="exam-step__group">
                <legend className="exam-step__group-title">专业课</legend>
                <p className="exam-step__hint">
                  全国统考的专业课可以直接选择；招生单位自命题的专业课不在全国统考目录里，请填在下方。
                </p>
                <div className="exam-options">
                  {groups.primary.map((option) => (
                    <Option
                      key={option.id}
                      type="checkbox"
                      value={option.id}
                      checked={professional.includes(option.id)}
                      onChange={() => toggleIn(option.id)}
                      title={option.name}
                      meta="完整学习功能已开放"
                      parts={moduleNames(catalog, option.id)}
                    />
                  ))}
                  {groups.national.map((option) => (
                    <Option
                      key={option.id}
                      type="checkbox"
                      value={option.id}
                      checked={professional.includes(option.id)}
                      onChange={() => toggleIn(option.id)}
                      title={option.name}
                      meta="内容建设中"
                    />
                  ))}
                </div>

                <div className="exam-step__group">
                  <h3 className="exam-step__group-title">自命题专业课</h3>
                  <p className="exam-step__hint">
                    名称由你自己填写。平台没有内置它的题库与真题：加入后你可以用自己上传的资料建立学习内容。
                  </p>
                  <div className="mt-4 flex flex-wrap items-end gap-3">
                    <div className="min-w-56 flex-1">
                      <TextField
                        label="科目名称"
                        name="exam-custom-subject"
                        type="text"
                        value={customDraft}
                        placeholder="例如：数据结构与算法（自命题）"
                        onChange={(event) => setCustomDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key !== 'Enter') return;
                          event.preventDefault();
                          addCustomName();
                        }}
                      />
                    </div>
                    <Button type="button" variant="secondary" onClick={addCustomName} disabled={!customDraft.trim()}>
                      添加科目
                    </Button>
                  </div>
                  {customNames.length ? (
                    <ul className="exam-custom-list">
                      {customNames.map((name) => (
                        <li key={name}>
                          <span className="text-body text-text-primary">{name}</span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setCustomNames((current) => current.filter((value) => value !== name))}
                            aria-label={`移除科目 ${name}`}
                          >
                            移除
                          </Button>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </fieldset>
            </>
          ) : null}

          {step === 1 ? (
            <>
              <fieldset className="exam-step__group">
                <legend className="exam-step__group-title">政治</legend>
                <p className="exam-step__hint">全国统考科目为思想政治理论。</p>
                <div className="exam-options">
                  {options.politics.map((option) => (
                    <Option
                      key={option.id}
                      type="checkbox"
                      value={option.id}
                      checked={politics.includes(option.id)}
                      onChange={() => toggleIn(option.id)}
                      title={option.name}
                      meta="内容建设中"
                    />
                  ))}
                </div>
              </fieldset>

              <fieldset className="exam-step__group">
                <legend className="exam-step__group-title">英语</legend>
                <p className="exam-step__hint">
                  英语（一）与英语（二）是两份不同的试卷，只选你实际要考的那一份；还没确定考哪一份就先不选，方案里暂时不会出现英语科目。
                </p>
                <div className="exam-options">
                  {options.english.map((option) => (
                    <Option
                      key={option.id}
                      type="radio"
                      name="exam-english"
                      value={option.id}
                      checked={english === option.id}
                      onChange={() => chooseOne(options.english, option.id)}
                      title={option.name}
                      meta="内容建设中"
                    />
                  ))}
                  <Option
                    type="radio"
                    name="exam-english"
                    value={NOT_CHOSEN}
                    checked={english === NOT_CHOSEN}
                    onChange={() => chooseOne(options.english, NOT_CHOSEN)}
                    // The label stands alone: a detail naming the two papers would put 英语（一）
                    // and 英语（二） inside this option's accessible name, so a screen reader
                    // reading the group would hear them on two options. The group's own hint
                    // already says which papers exist and what not choosing means.
                    title="暂未确定英语科目"
                  />
                </div>
              </fieldset>

              <fieldset className="exam-step__group">
                <legend className="exam-step__group-title">数学</legend>
                <p className="exam-step__hint">数学（一）／（二）／（三）是不同要求的试卷。</p>
                <div className="exam-options">
                  {options.math.map((option) => (
                    <Option
                      key={option.id}
                      type="radio"
                      name="exam-math"
                      value={option.id}
                      checked={math === option.id}
                      onChange={() => chooseOne(options.math, option.id)}
                      title={option.name}
                      meta="内容建设中"
                    />
                  ))}
                  <Option
                    type="radio"
                    name="exam-math"
                    value={NO_UNIFIED_MATH}
                    checked={math === NO_UNIFIED_MATH}
                    onChange={() => chooseOne(options.math, NO_UNIFIED_MATH)}
                    title="不考统考数学"
                    detail="不选择任何统考数学试卷；专业课之外的数学要求由招生单位决定。"
                  />
                </div>
              </fieldset>
            </>
          ) : null}

          {step === 2 ? (
            <div className="exam-confirm">
              <p className="exam-confirm__headline">{yearLabel}</p>
              <p className="exam-confirm__direction">备考方向 · {selectedTrack?.display_name ?? '未选择'}</p>

              <ul className="exam-confirm__subjects">
                {hasSelection ? (
                  <>
                    {politics.map((id) => (
                      <li key={id}>{optionName(options.politics, id)}</li>
                    ))}
                    {english ? <li key={english}>{optionName(options.english, english)}</li> : null}
                    {math ? <li key={math}>{optionName(options.math, math)}</li> : null}
                    {professional.map((id) => (
                      <li key={id}>{optionName(options.professional, id)}</li>
                    ))}
                    {customNames.map((name) => (
                      <li key={name}>
                        {name} <span>· 自命题</span>
                      </li>
                    ))}
                  </>
                ) : (
                  <li>
                    尚未选择考试科目 <span>· 返回上一步选择，或先保存稍后补充</span>
                  </li>
                )}
              </ul>

              <p className="exam-confirm__note">{EXAM_PLAN_DISCLAIMER}</p>

              {hasSelection ? null : (
                <StatusNote tone="warning" className="mt-4">
                  还没有选择任何考试科目。保存后考研首页会提示你继续补充。
                </StatusNote>
              )}

              {saveError ? (
                <StatusNote tone="danger" className="mt-4">
                  {saveError}
                </StatusNote>
              ) : null}

              <div className="exam-confirm__actions">
                <Button type="submit" disabled={save.isPending}>
                  {save.isPending ? '正在保存…' : '确认考试方案'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setStep(LAST_STEP - 1)}>
                  返回修改
                </Button>
              </div>
            </div>
          ) : null}
        </section>

        {step < LAST_STEP ? (
          <div className="exam-step__nav">
            {step > 0 ? (
              <Button type="button" variant="secondary" onClick={() => setStep(step - 1)}>
                上一步
              </Button>
            ) : null}
            <Button type="button" onClick={() => setStep(step + 1)}>
              下一步
            </Button>
          </div>
        ) : null}
      </form>

      {pendingCombination ? (
        <ConfirmDialog
          title="替换当前科目组合？"
          description={`使用常见组合会移除你已选择的：${removedBy(subjects, pendingCombination, options)}`}
          confirmLabel="替换"
          cancelLabel="保留我的选择"
          onConfirm={() => {
            setSubjects([...pendingCombination]);
            setPendingCombination(null);
          }}
          onCancel={() => setPendingCombination(null)}
        />
      ) : null}
    </ExamPageShell>
  );
}

const STEP_HINTS: readonly string[] = [
  '备考方向只帮你生成常见组合；专业课由你自己确认。',
  '公共课按科目逐项确认。英语和数学考哪一种由你选择。',
  '这是你确认后的考试方案，它决定你在考研学习里的学习范围。',
];

function optionName(options: readonly ExamSubjectOption[], id: string): string {
  return options.find((option) => option.id === id)?.name ?? id;
}

/** The name of any catalogue subject, whichever line of the plan it belongs on. */
function anyOptionName(all: ReturnType<typeof planOptions>, id: string): string {
  return optionName(
    [...all.politics, ...all.english, ...all.math, ...all.professional],
    id,
  );
}

/** The catalogue's own part names for a subject this build has modules for. */
function moduleNames(catalog: ExamCatalog, subjectId: string): readonly string[] {
  const subject = catalog.subjects.find((item) => item.id === subjectId);
  return subject ? subject.modules.map((module) => module.display_name) : [];
}

/** Which of the learner's own subjects a suggested combination would drop, named rather than id'd. */
function removedBy(
  current: readonly string[],
  next: readonly string[],
  options: ReturnType<typeof planOptions>,
): string {
  const kept = new Set(next);
  return current
    .filter((id) => !kept.has(id))
    .map((id) => anyOptionName(options, id))
    .join(' · ');
}

/**
 * One selectable line of a group.
 *
 * The availability note states a fact the learner needs before choosing — a framework-only subject
 * is genuinely selectable, because the profile records the goal, but its content is not open yet,
 * and finding that out on the page they were sent to would be too late.
 */
function Option({
  type,
  name,
  value,
  checked,
  onChange,
  title,
  detail,
  meta,
  parts,
}: {
  type: 'radio' | 'checkbox';
  name?: string;
  value: string;
  checked: boolean;
  onChange: () => void;
  title: string;
  detail?: string;
  meta?: string;
  /** The subject's own parts, shown only for the subject that actually has them. */
  parts?: readonly string[];
}) {
  return (
    <label className="exam-option">
      <input type={type} name={name} value={value} checked={checked} onChange={onChange} />
      <span className="exam-option__text">
        <strong>{title}</strong>
        {detail ? <small>{detail}</small> : null}
        {parts?.length ? <span className="exam-option__parts">{parts.join(' · ')}</span> : null}
      </span>
      {meta ? <span className="exam-option__meta">{meta}</span> : null}
    </label>
  );
}

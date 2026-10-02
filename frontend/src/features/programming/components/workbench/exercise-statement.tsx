import type { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { exerciseRoot } from './workbench-model';

/**
 * The题面, laid out as fields the backend actually sends.
 *
 * The payload is a dict of Chinese fields (`statement`, `input_format`, `output_format`,
 * `constraints`, `public_samples`, …), so they are rendered as a readable problem rather than
 * dumped as JSON. Hints and background stay folded: they are support a learner asks for, and
 * unfolding them on arrival would answer the exercise for them.
 */

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

/**
 * The first of several field names a backend sample actually carries, as a plain string.
 *
 * The catalogue has used more than one spelling for the same value across its versions, so the
 * caller passes them in priority order. A value of `0` or `false` is text like any other — only
 * `undefined`/`null` fall through, which is why this does not use a truthiness check.
 */
function sampleText(sample: Record<string, unknown>, keys: readonly string[]): string | undefined {
  for (const key of keys) {
    const value = sample[key];
    if (value === undefined || value === null) continue;
    const rendered = String(value);
    if (rendered.trim()) return rendered.replace(/\n$/, '');
  }
  return undefined;
}

/** `stdin_text` / `expected_stdout` are the fields the catalogue stores; the rest are older names. */
const SAMPLE_INPUT_KEYS = ['stdin_text', 'stdin', 'input'] as const;
const SAMPLE_OUTPUT_KEYS = ['expected_stdout', 'expect_stdout', 'stdout', 'output', 'expected_output'] as const;

export function ExerciseStatement({ payload, recovery }: { payload: unknown; recovery?: ReactNode }) {
  const exercise = exerciseRoot(payload);
  const title = text(exercise.title);
  const statement = text(exercise.statement) ?? text(exercise.problem_statement) ?? text(exercise.summary);
  const inputFormat = text(exercise.input_format);
  const outputFormat = text(exercise.output_format);
  const constraints = text(exercise.constraints);
  const hints = text(exercise.hints);
  const background = text(exercise.background_knowledge);
  const samples = Array.isArray(exercise.public_samples)
    ? (exercise.public_samples as Array<Record<string, unknown>>).filter((sample) => typeof sample === 'object' && sample !== null)
    : [];

  return (
    <section aria-labelledby="wb-statement-title">
      <div className="wb-statement__head">
        <h2 id="wb-statement-title" className="wb-statement__title">
          {title ?? '练习题面'}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          {text(exercise.difficulty) ? <Badge>{text(exercise.difficulty)}</Badge> : null}
          {text(exercise.source_label) ? <Badge tone="neutral">{text(exercise.source_label)}</Badge> : null}
        </div>
      </div>

      {statement ? (
        <p className="wb-statement__body">{statement}</p>
      ) : (
        <div className="mt-3">
          <p className="wb-statement__value">题目信息暂不完整，这里无法显示题面。</p>
          {recovery ? <div className="mt-3 flex flex-wrap gap-3">{recovery}</div> : null}
        </div>
      )}

      {inputFormat ? (
        <div className="wb-statement__field">
          <p className="wb-statement__label">输入</p>
          <p className="wb-statement__value">{inputFormat}</p>
        </div>
      ) : null}
      {outputFormat ? (
        <div className="wb-statement__field">
          <p className="wb-statement__label">输出</p>
          <p className="wb-statement__value">{outputFormat}</p>
        </div>
      ) : null}
      {constraints ? (
        <div className="wb-statement__field">
          <p className="wb-statement__label">约束</p>
          <p className="wb-statement__value">{constraints}</p>
        </div>
      ) : null}

      {samples.length ? (
        <div className="wb-statement__field">
          <p className="wb-statement__label">示例</p>
          <ul className="wb-samples">
            {samples.map((sample, index) => (
              <li key={String(sample.id ?? index)} className="wb-sample">
                <div className="wb-sample__grid sm:grid-cols-2">
                  <div>
                    <p className="wb-sample__label">输入</p>
                    <pre className="wb-sample__value">{sampleText(sample, SAMPLE_INPUT_KEYS) ?? '—'}</pre>
                  </div>
                  <div>
                    <p className="wb-sample__label">期望输出</p>
                    <pre className="wb-sample__value">{sampleText(sample, SAMPLE_OUTPUT_KEYS) ?? '—'}</pre>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {hints || background ? (
        <div className="wb-statement__field space-y-2">
          {background ? (
            <details>
              <summary className="text-body text-text-secondary">背景知识</summary>
              <p className="wb-statement__value">{background}</p>
            </details>
          ) : null}
          {hints ? (
            <details>
              <summary className="text-body text-text-secondary">提示（先自己尝试再看）</summary>
              <p className="wb-statement__value">{hints}</p>
            </details>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

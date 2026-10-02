import { ApiRequestError } from '@/features/exam/api/content-status';
import { serverErrorCode } from '@/lib/api/server-message';

/**
 * The stable code the code-execution gate answers with when it refuses to run learner code.
 *
 * It is the deployment's state, not the learner's: SECURITY_S0 keeps every execution entry point
 * fail-closed until a verified sandbox is present, so 运行 / 运行测试 / 提交 get this refusal in
 * production by design. Kept here as the one place the workbench's UI names it.
 */
export const CODE_EXECUTION_UNAVAILABLE = 'code_execution_unavailable';

/**
 * What a learner reads when the run environment is off — the one place the code is given words.
 *
 * It does not describe their code as wrong: nothing was judged. It says the code was kept and the
 * environment will come back, because the judge writes the buffer to the project BEFORE it asks to
 * run, so by the time this refusal arrives the draft is already saved.
 */
export const CODE_EXECUTION_UNAVAILABLE_MESSAGE =
  '代码运行环境当前不可用，你的代码已自动保存。可以继续编辑，运行环境恢复后再执行。';

/**
 * The sentence to show when a run / test / submit call fails, or `undefined` to use the caller's
 * own.
 *
 * Only the stable `code` selects it — the server's own `message` is never passed through — and an
 * unavailable run environment is picked out from the pool of ordinary failures because it is not
 * one: it is a property of the deployment the learner can do nothing about. Everything else stays
 * as the caller had it, so this mapping cannot change how any other error reads.
 */
export function judgeFailureMessage(error: unknown): string | undefined {
  if (!(error instanceof ApiRequestError)) return undefined;
  if (serverErrorCode(error.detail) !== CODE_EXECUTION_UNAVAILABLE) return undefined;
  return CODE_EXECUTION_UNAVAILABLE_MESSAGE;
}

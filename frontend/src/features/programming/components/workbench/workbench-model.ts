import type { BankExercise, ExerciseWorkspace, ProjectFile } from '../../api/programming';

/**
 * The workbench's pure readings of what the bank and the project actually contain.
 *
 * Everything here is a mapping, a grouping or a comparison over fields the backend sent — no
 * value is derived from a title, no status is guessed, and nothing is invented for a field that
 * is absent. Keeping it out of the components is what lets the rules be tested without a DOM.
 */

export type ExerciseStatus = 'passed' | 'needs_work' | 'not_started';

/** The product status the endpoint publishes per exercise (`personal_progress.personal_status`). */
export function exerciseStatus(item: BankExercise): ExerciseStatus {
  const progress = personalProgress(item);
  const status = progress?.personal_status;
  if (status === 'passed') return 'passed';
  if (status === 'needs_work' || status === 'needs_improvement') return 'needs_work';
  return 'not_started';
}

export function personalProgress(item: BankExercise): Record<string, unknown> | undefined {
  const progress = item.personal_progress;
  return typeof progress === 'object' && progress !== null && !Array.isArray(progress)
    ? (progress as Record<string, unknown>)
    : undefined;
}

export const STATUS_LABEL: Readonly<Record<ExerciseStatus, string>> = {
  passed: '已完成',
  needs_work: '做错过',
  not_started: '未完成',
};

/** The exercise's own title. An exercise with no title is unnamed — its database id is not a name. */
export function exerciseTitle(item: BankExercise, fallback: string): string {
  for (const key of ['title', 'name', 'exercise_title'] as const) {
    const value = item[key];
    if (typeof value === 'string' && value.trim()) return value;
  }
  return fallback;
}

export function difficultyOf(item: BankExercise): string | undefined {
  const value = item.difficulty;
  return typeof value === 'string' && value.trim() ? value : undefined;
}

export function exerciseIdOf(item: BankExercise): number | undefined {
  const value = item.id;
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

/**
 * The chapter an exercise is filed under.
 *
 * `curriculum_module` is the catalogue's own grouping and is present on every exercise the bank
 * serves; the first canonical knowledge point is the fallback when a future row omits it, and an
 * exercise that names neither goes to 其他题目 rather than being dropped from the rail.
 */
export function chapterOf(item: BankExercise): string {
  const module = item.curriculum_module;
  if (typeof module === 'string' && module.trim()) return module;
  const first = firstKnowledgePoint(item);
  return first?.title ?? '其他题目';
}

export function firstKnowledgePoint(item: BankExercise): { code: string; title: string } | undefined {
  const points = item.knowledge_points;
  if (!Array.isArray(points)) return undefined;
  for (const point of points) {
    if (typeof point !== 'object' || point === null) continue;
    const record = point as Record<string, unknown>;
    const title = typeof record.title === 'string' ? record.title : '';
    if (!title.trim()) continue;
    return { code: typeof record.code === 'string' ? record.code : '', title };
  }
  return undefined;
}

export type ExerciseGroup = { key: string; title: string; items: BankExercise[] };

/**
 * The rail's chapters, in the order the bank listed them.
 *
 * Insertion order is the bank's own order (first-party originals first, then by status and id), so
 * a chapter appears where its first exercise does and the rail reads in the same order as the API.
 */
export function groupByChapter(items: readonly BankExercise[]): ExerciseGroup[] {
  const groups: ExerciseGroup[] = [];
  const byKey = new Map<string, ExerciseGroup>();
  for (const item of items) {
    const title = chapterOf(item);
    let group = byKey.get(title);
    if (!group) {
      group = { key: title, title, items: [] };
      byKey.set(title, group);
      groups.push(group);
    }
    group.items.push(item);
  }
  return groups;
}

/** When one exercise was last touched, off the progress the bank carries. 0 when never. */
export function lastTouchedMs(item: BankExercise): number {
  const progress = personalProgress(item);
  if (!progress) return 0;
  for (const key of ['last_submit_at', 'last_test_at', 'last_run_at']) {
    const value = progress[key];
    if (typeof value === 'string') {
      const time = new Date(value).getTime();
      if (Number.isFinite(time)) return time;
    }
  }
  return 0;
}

/**
 * The exercise to open when the address names none: the one touched most recently that is not
 * already passed, otherwise the most recent, otherwise the bank's first row. Nothing is claimed
 * about an exercise nobody has opened — with no history at all this is simply the first one.
 */
export function resumeExerciseId(items: readonly BankExercise[]): number | undefined {
  const touched = items
    .map((item) => ({ id: exerciseIdOf(item), at: lastTouchedMs(item), status: exerciseStatus(item) }))
    .filter((entry): entry is { id: number; at: number; status: ExerciseStatus } => entry.id !== undefined && entry.at > 0)
    .sort((left, right) => right.at - left.at);
  const target = touched.find((entry) => entry.status !== 'passed') ?? touched[0];
  if (target) return target.id;
  return items.map(exerciseIdOf).find((id): id is number => id !== undefined);
}

/* ------------------------------------------------------------------ the题面 */

function sampleList(payload: unknown): Array<Record<string, unknown>> {
  const exercise = exerciseRoot(payload);
  const samples = exercise.public_samples;
  if (!Array.isArray(samples)) return [];
  return samples.filter((sample): sample is Record<string, unknown> => typeof sample === 'object' && sample !== null);
}

/** One level into `{exercise: {...}}`, which is how the detail endpoint wraps its payload. */
export function exerciseRoot(payload: unknown): Record<string, unknown> {
  if (typeof payload !== 'object' || payload === null) return {};
  const root = payload as Record<string, unknown>;
  const inner = root.exercise;
  return typeof inner === 'object' && inner !== null ? (inner as Record<string, unknown>) : root;
}

/**
 * The ids of the题面's own visible samples — what `test` must be told to run.
 *
 * The test endpoint runs the sample ids it is given and rejects the request when it is given
 * none, so the ids come from the same payload the samples are rendered from rather than from a
 * second read that could disagree with it.
 */
export function publicSampleIds(payload: unknown): string[] {
  return sampleList(payload).flatMap((sample) => {
    const id = sample.id;
    return id === undefined || id === null || id === '' ? [] : [String(id)];
  });
}

/* ------------------------------------------------------------------ the open project */

/**
 * Which file the editor is about, and what the题面 shipped it as.
 *
 * The project's `entry_file` is the file the runtime compiles and runs, so that is the file the
 * editor edits. `starter` is the same file's original content from the exercise's own starter
 * files — what 重置代码 restores — and is absent when the exercise ships no starter for that path,
 * in which case there is nothing honest to reset to.
 */
export function entryFileOf(workspace: ExerciseWorkspace): { file: ProjectFile; starter?: string } | undefined {
  const files = workspace.project.files;
  if (!files.length) return undefined;
  const entry = workspace.project.entry_file;
  const file = files.find((candidate) => candidate.relative_path === entry) ?? files[0];
  if (!file) return undefined;
  const starter = workspace.starterFiles.find((candidate) => candidate.path === file.relative_path)?.content;
  return { file, starter };
}

/* ------------------------------------------------------------------ judge results */

/**
 * The last test's cases, in the shape the AI coach's endpoint reads.
 *
 * The judge reports `{passed_count, total_count, cases}`, while `/code/analyze` reads
 * `{total, passed, results}` — so this is the one translation between them, kept here so neither
 * shape leaks into the other's code.
 */
export function coachTestPayload(result: unknown): Record<string, unknown> | undefined {
  if (typeof result !== 'object' || result === null) return undefined;
  const record = result as Record<string, unknown>;
  const cases = Array.isArray(record.cases) ? record.cases : [];
  return {
    total: typeof record.total_count === 'number' ? record.total_count : cases.length,
    passed: typeof record.passed_count === 'number' ? record.passed_count : 0,
    results: cases.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null),
  };
}

export function numberField(value: unknown, key: string): number | undefined {
  if (typeof value !== 'object' || value === null) return undefined;
  const raw = (value as Record<string, unknown>)[key];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : undefined;
}

export function stringField(value: unknown, key: string): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined;
  const raw = (value as Record<string, unknown>)[key];
  return typeof raw === 'string' && raw.trim() ? raw : undefined;
}

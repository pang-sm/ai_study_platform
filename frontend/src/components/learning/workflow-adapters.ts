export type StrongReasoningResponse = {
  evidence: Array<{ citation: string; excerpt?: string }>;
  usage?: { estimated?: number; actual?: number };
};

export type ProgrammingAgentWorkflow = {
  steps: Array<{ name: string; status: 'pending' | 'running' | 'complete' | 'failed'; evidence?: string }>;
};

export type ReviewItem = {
  id: string;
  space: 'course_learning' | 'exam_11408' | 'programming';
  sourceIdentity: string;
  context: string;
  reason: string;
  dueAt?: string;
  status: 'due' | 'completed';
  href: string;
};

export type ReviewSummary = { dueCount: number; completedCount: number };

export type ReviewAdapterResult = { available: boolean; items: ReviewItem[]; summary?: ReviewSummary };

export type ExecutionEvidence = {
  kind: 'run' | 'test' | 'submit';
  stdout?: string;
  stderr?: string;
  passed?: boolean;
};

function stringField(value: Record<string, unknown>, field: 'stdout' | 'stderr'): string | undefined {
  return typeof value[field] === 'string' ? value[field] : undefined;
}

export function executionEvidence(kind: ExecutionEvidence['kind'], response: unknown): ExecutionEvidence {
  const value = typeof response === 'object' && response !== null ? response as Record<string, unknown> : {};
  return {
    kind,
    stdout: stringField(value, 'stdout'),
    stderr: stringField(value, 'stderr'),
    passed: typeof value.passed === 'boolean' ? value.passed : undefined,
  };
}

export function reviewAdapterUnavailable(): ReviewAdapterResult {
  return { available: false, items: [], summary: undefined };
}

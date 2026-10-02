import { createFileRoute } from '@tanstack/react-router';
import { ProgrammingWorkbenchPage } from '@/features/programming/components/programming-workbench-page';

/** 编程学习's front door: today's work, where the learner stands, and where else to go. */
export const Route = createFileRoute('/programming/')({ component: ProgrammingWorkbenchPage });

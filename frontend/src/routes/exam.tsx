import { createFileRoute } from '@tanstack/react-router';
import { ExamWorldPage } from '@/features/exam/exam-slice';
export const Route = createFileRoute('/exam')({ component: ExamWorldPage });

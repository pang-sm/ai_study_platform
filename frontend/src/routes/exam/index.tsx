import { createFileRoute } from '@tanstack/react-router';
import { ExamHomePage } from '@/features/exam/components/exam-home-page';

export const Route = createFileRoute('/exam/')({ component: ExamHomePage });

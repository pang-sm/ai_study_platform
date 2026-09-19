import { createFileRoute } from '@tanstack/react-router';
import { ExamSetupPage } from '@/features/exam/components/exam-product-pages';

export const Route = createFileRoute('/exam/setup')({ component: ExamSetupPage });

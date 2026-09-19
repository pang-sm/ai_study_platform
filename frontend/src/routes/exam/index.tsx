import { createFileRoute } from '@tanstack/react-router';
import { MyExamPage } from '@/features/exam/components/exam-product-pages';

export const Route = createFileRoute('/exam/')({ component: MyExamPage });

import { createFileRoute } from '@tanstack/react-router';
import { SubjectsCatalogPage } from '@/features/exam/components/exam-product-pages';

export const Route = createFileRoute('/exam/subjects/')({ component: SubjectsCatalogPage });

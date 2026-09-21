import { createFileRoute } from '@tanstack/react-router';
import { ProgrammingHomePage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/')({ component: ProgrammingHomePage });

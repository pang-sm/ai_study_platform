import { createFileRoute } from '@tanstack/react-router';
import { Cs408Workspace } from '@/features/exam/components/cs408-workspace';

export const Route = createFileRoute('/exam/cs408/')({ component: Cs408Workspace });

import { createFileRoute } from '@tanstack/react-router';
import { WorkbenchPage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/$language/projects/$projectId')({ component: ProgrammingWorkbenchRoute });
function ProgrammingWorkbenchRoute() { const { language, projectId } = Route.useParams(); return <WorkbenchPage language={language} exerciseId={Number(projectId)} />; }

import { createFileRoute } from '@tanstack/react-router';
import { Cs408StudyPlanWorkspace } from '@/features/exam/components/cs408-study-plan-workspace';

export const Route = createFileRoute('/exam/cs408/plan')({ component: Cs408PlanRoute });
function Cs408PlanRoute() { return <Cs408StudyPlanWorkspace />; }

import { createFileRoute } from '@tanstack/react-router';
import { SubjectDetailPage } from '@/features/exam/components/exam-product-pages';

export const Route = createFileRoute('/exam/subjects/$subjectId')({ component: SubjectRoute });

function SubjectRoute() { return <SubjectDetailPage subjectId={Route.useParams().subjectId} />; }

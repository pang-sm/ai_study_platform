import { createFileRoute } from '@tanstack/react-router';
import { RecordsPage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/$language/records')({ component: ProgrammingRecordsRoute });
function ProgrammingRecordsRoute() { return <RecordsPage language={Route.useParams().language} />; }

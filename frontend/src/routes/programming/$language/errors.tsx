import { createFileRoute } from '@tanstack/react-router';
import { ErrorsPage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/$language/errors')({ component: ProgrammingErrorsRoute });
function ProgrammingErrorsRoute() { return <ErrorsPage language={Route.useParams().language} />; }

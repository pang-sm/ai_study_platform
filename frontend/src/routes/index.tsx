import { createFileRoute } from '@tanstack/react-router';
import { CheckCircle2 } from 'lucide-react';
import { Container } from '@/components/ui/container';
import { Button } from '@/components/ui/button';

export const Route = createFileRoute('/')({
  component: IndexRoute,
});

function IndexRoute() {
  return (
    <Container className="py-12">
      <div className="flex flex-col items-start gap-4">
        <CheckCircle2 className="size-8 text-success" aria-hidden="true" />
        <h1 className="text-page-title font-semibold text-text-primary">智学平台</h1>
        <p className="text-body text-text-secondary">Frontend architecture initialized.</p>
        <Button>开始学习</Button>
      </div>
    </Container>
  );
}

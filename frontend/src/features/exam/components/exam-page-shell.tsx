import type { ReactNode } from 'react';
import { Container } from '@/components/ui/container';
import { ExamContextNav, type ExamContextItem } from '@/features/exam/components/exam-context-nav';
import './exam-product-pages.css';

export function ExamPageShell({ activeItem, children }: { activeItem: ExamContextItem; children: ReactNode }) {
  return (
    <div className="exam-shell">
      <div className="exam-shell__masthead">
        <Container className="exam-shell__masthead-inner">
          <p>考研学习</p>
          <small>全国统考 · 学习空间</small>
        </Container>
      </div>
      <ExamContextNav activeItem={activeItem} />
      <Container className="exam-page">{children}</Container>
    </div>
  );
}

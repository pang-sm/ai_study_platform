import { ArrowLeft } from 'lucide-react';
import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';

export function ContentUnavailableState({ subjectName, selected = false }: { subjectName: string; selected?: boolean }) {
  return (
    <section className="exam-status-dossier" aria-labelledby="content-unavailable-title">
      <div className="exam-status-dossier__geometry" aria-hidden="true" />
      <div className="exam-status-dossier__content">
        <p className="exam-kicker">内容状态</p>
        <div className="exam-status-dossier__symbol" aria-hidden="true">△ 01</div>
        <h1 id="content-unavailable-title">{subjectName}内容建设中</h1>
        <p className="mt-5 text-body">
          已开放加入我的备考，学习内容将后续开放。
        </p>
        <p className="mt-3 text-metadata text-text-secondary">
          {selected ? '这门科目已加入你的备考范围。' : '你可在备考设置中确认是否加入这门科目。'}
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild variant="secondary">
            <Link to="/exam/subjects"><ArrowLeft className="size-4" aria-hidden="true" />返回科目</Link>
          </Button>
          <Button asChild variant="ghost">
            <Link to="/exam/setup">编辑备考设置</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}

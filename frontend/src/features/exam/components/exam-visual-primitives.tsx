import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function TechnicalRule({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cn("exam-rule", className)} />;
}

export function DossierHeader({
  index,
  eyebrow,
  title,
  children,
  dark = false,
}: {
  index?: string;
  eyebrow: string;
  title: string;
  children?: ReactNode;
  dark?: boolean;
}) {
  return (
    <header className={cn("exam-dossier", !index && "exam-dossier--no-index", dark && "exam-dossier--dark")}>
      {index ? <div className="exam-dossier__index" aria-hidden="true">{index}</div> : null}
      <div className="exam-dossier__content">
        <p className="exam-kicker">{eyebrow}</p>
        <h1 className="exam-dossier__title">{title}</h1>
        {children}
      </div>
      <TechnicalRule className="exam-dossier__rule" />
    </header>
  );
}

export function IndexRow({
  index,
  title,
  meta,
  status,
  action,
  active = false,
}: {
  index: string;
  title: string;
  meta: ReactNode;
  status?: ReactNode;
  action: ReactNode;
  active?: boolean;
}) {
  return (
    <li className={cn("exam-index-row", active && "exam-index-row--active")}>
      <span className="exam-index-row__number" aria-hidden="true">{index}</span>
      <div className="exam-index-row__identity">
        <h3>{title}</h3>
        <div className="exam-index-row__meta">{meta}</div>
      </div>
      <div className="exam-index-row__status">{status}</div>
      <div className="exam-index-row__action">{action}</div>
    </li>
  );
}

const configurationSteps = ["备考方向", "实际科目", "目标年份", "确认"];

export function ConfigurationStepRail() {
  return (
    <ol className="exam-step-rail" aria-label="备考设置步骤">
      {configurationSteps.map((label, index) => (
        <li key={label} className={index === 0 ? "is-active" : undefined}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          <strong>{label}</strong>
        </li>
      ))}
    </ol>
  );
}

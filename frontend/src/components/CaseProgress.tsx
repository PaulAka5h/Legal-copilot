import { Icon } from "@/components/Icon";
import { numberFor, type Language } from "@/lib/i18n";

export type CaseProgressStage = {
  id: string;
  label: string;
  note: string;
  state: "complete" | "current" | "upcoming";
};

/** Share of stages completed. The current stage is in progress, not reached. */
export function progressFor(stages: Pick<CaseProgressStage, "state">[]) {
  const total = stages.length;
  const reached = stages.filter((stage) => stage.state === "complete").length;

  return {
    reached,
    total,
    percent: total ? Math.round((reached / total) * 100) : 0,
  };
}

export function CaseProgress({
  language,
  stages,
  completeLabel,
}: {
  language: Language;
  stages: CaseProgressStage[];
  completeLabel: string;
}) {
  const { percent } = progressFor(stages);

  return (
    <div className="progress-wrap">
      <div className="progress-track" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="stage-list">
        {stages.map((stage, index) => (
          <div className={`stage ${stage.state}`} key={stage.id}>
            <span className="stage-dot">
              {stage.state === "complete" ? (
                <Icon name="check" size={14} />
              ) : (
                numberFor(language, index + 1)
              )}
            </span>
            <b>{stage.label}</b>
            <small>{stage.note}</small>
            {stage.state === "complete" ? (
              <span className="sr-only">{completeLabel}</span>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

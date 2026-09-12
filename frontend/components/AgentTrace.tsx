interface AgentTraceProps {
  goal: string;
  skill: string | null;
  questionNumber: number;
  evidenceGap: string | null;
  nextAction: string | null;
  hasAnswer: boolean;
}

export default function AgentTrace({
  goal,
  skill,
  questionNumber,
  evidenceGap,
  nextAction,
  hasAnswer,
}: AgentTraceProps) {
  const observation = hasAnswer
    ? `Candidate submitted an answer for question ${questionNumber - 1}.`
    : "Interview started. Waiting for candidate response.";

  const decision = hasAnswer
    ? "Evaluate the response and select the next useful question."
    : "Collect evidence about the candidate's current skill.";

  const action = nextAction || "Ask the current interview question.";

  const expectedInformation = evidenceGap
    ? `Obtain evidence to address: ${evidenceGap}`
    : "Evaluate the candidate's knowledge and communication.";

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">
            Agent Trace
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            Decision context
          </p>
        </div>

        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-500/20 text-blue-400">
          AI
        </div>
      </div>

      {/* Goal */}
      <TraceItem
        number="01"
        title="Current Goal"
        value={goal}
      />

      {/* Skill */}
      <TraceItem
        number="02"
        title="Current Skill"
        value={skill || "Not available"}
      />

      {/* Observation */}
      <TraceItem
        number="03"
        title="Observation"
        value={observation}
      />

      {/* Evidence Gap */}
      <TraceItem
        number="04"
        title="Evidence Gap"
        value={evidenceGap || "No evidence gap detected"}
      />

      {/* Decision */}
      <TraceItem
        number="05"
        title="Decision"
        value={decision}
      />

      {/* Action */}
      <TraceItem
        number="06"
        title="Action"
        value={action}
      />

      {/* Expected Information */}
      <TraceItem
        number="07"
        title="Expected Information"
        value={expectedInformation}
        last
      />
    </div>
  );
}


interface TraceItemProps {
  number: string;
  title: string;
  value: string;
  last?: boolean;
}

function TraceItem({
  number,
  title,
  value,
  last = false,
}: TraceItemProps) {
  return (
    <div
      className={`relative py-4 ${
        !last ? "border-b border-slate-800" : ""
      }`}
    >
      <div className="flex gap-3">

        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs text-slate-400">
          {number}
        </div>

        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {title}
          </p>

          <p className="mt-1 text-sm leading-6 text-slate-300">
            {value}
          </p>
        </div>

      </div>
    </div>
  );
}
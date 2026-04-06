import { StepRecord } from '../types/api';

interface StepTimelineProps {
  steps: StepRecord[];
}

export function StepTimeline({ steps }: StepTimelineProps) {
  if (steps.length === 0) {
    return <div className="step-timeline empty">No steps yet</div>;
  }

  return (
    <div className="step-timeline">
      <h3>Timeline</h3>
      <div className="steps-list">
        {steps.map((step) => (
          <div key={step.step_id} className={`step-item status-${step.status}`}>
            <div className="step-header">
              <span className="step-id">Step {step.step_id}</span>
              <span className="step-status">{step.status}</span>
            </div>
            {step.reasoning && <div className="step-reasoning">{step.reasoning}</div>}
            {step.function_calls.length > 0 && (
              <div className="step-actions">
                {step.function_calls.map((call, idx) => (
                  <div key={`${call.name}-${idx}`} className="step-action">
                    <code>{call.name}</code>
                  </div>
                ))}
              </div>
            )}
            {step.error_message && <div className="step-error">{step.error_message}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

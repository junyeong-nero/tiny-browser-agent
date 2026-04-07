import type { SessionSnapshot, StepRecord, VerificationItem } from './types/api';

export type PreviewMode = { kind: 'current' } | { kind: 'step'; stepId: number };

export interface StepGroup {
  id: string;
  label: string;
  summary: string | null;
  steps: StepRecord[];
}

export function buildArtifactUrl(
  artifactsBaseUrl: string | null | undefined,
  artifactPath: string | null | undefined,
): string | null {
  if (!artifactsBaseUrl || !artifactPath) {
    return null;
  }

  return `${artifactsBaseUrl}/${artifactPath}`;
}

export function getRequestText(snapshot: SessionSnapshot | null | undefined): string | null {
  if (!snapshot) {
    return null;
  }

  if (snapshot.request_text) {
    return snapshot.request_text;
  }

  const firstUserMessage = snapshot.messages.find((message) => message.role === 'user');
  return firstUserMessage?.text ?? null;
}

export function getRunSummary(snapshot: SessionSnapshot | null | undefined): string | null {
  if (!snapshot) {
    return null;
  }

  return snapshot.run_summary ?? snapshot.final_reasoning ?? snapshot.last_reasoning ?? null;
}

export function getFinalResultSummary(snapshot: SessionSnapshot | null | undefined): string | null {
  if (!snapshot) {
    return null;
  }

  return snapshot.final_result_summary ?? snapshot.final_reasoning ?? snapshot.last_reasoning ?? null;
}

export function getValidVerificationItems(
  items: VerificationItem[] | null | undefined,
): VerificationItem[] {
  return (items ?? []).filter((item) => item.source_step_id != null);
}

export function groupStepsForDisplay(steps: StepRecord[]): StepGroup[] {
  if (steps.length === 0) {
    return [];
  }

  const hasPhaseMetadata = steps.some((step) => step.phase_id);
  if (!hasPhaseMetadata) {
    return [
      {
        id: 'all-steps',
        label: '전체 과정 보기',
        summary: null,
        steps,
      },
    ];
  }

  const groups: StepGroup[] = [];
  for (const step of steps) {
    const phaseId = step.phase_id ?? `step-${step.step_id}`;
    const previousGroup = groups.length > 0 ? groups[groups.length - 1] : null;

    if (previousGroup && previousGroup.id === phaseId) {
      previousGroup.steps.push(step);
      if (!previousGroup.summary && step.phase_summary) {
        previousGroup.summary = step.phase_summary;
      }
      continue;
    }

    groups.push({
      id: phaseId,
      label: step.phase_label ?? step.user_visible_label ?? `Step ${step.step_id}`,
      summary: step.phase_summary ?? null,
      steps: [step],
    });
  }

  return groups;
}

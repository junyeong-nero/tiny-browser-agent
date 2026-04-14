import type { SessionSnapshot, StepRecord, VerificationGroup, VerificationItem } from './types/api';

export type PreviewMode = { kind: 'current' } | { kind: 'step'; stepId: number };

export interface StepGroup {
  id: string;
  run_id?: string | null;
  label: string;
  summary: string | null;
  steps: StepRecord[];
}

export interface RunGroup<TGroup extends StepGroup | VerificationGroup = StepGroup | VerificationGroup> {
  id: string;
  runId: string | null;
  label: string;
  groups: TGroup[];
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

export function getRelevantRunId(
  snapshot: SessionSnapshot | null | undefined,
  verificationPayload?: {
    current_run_id?: string | null;
    last_completed_run_id?: string | null;
    grouped_steps?: VerificationGroup[] | null;
  } | null,
  steps: StepRecord[] = [],
): string | null {
  const latestGroupedRunId = verificationPayload?.grouped_steps?.[verificationPayload.grouped_steps.length - 1]?.run_id;
  const latestStepRunId = steps[steps.length - 1]?.run_id ?? null;
  return (
    snapshot?.current_run_id
    ?? verificationPayload?.current_run_id
    ?? latestGroupedRunId
    ?? latestStepRunId
    ?? snapshot?.last_completed_run_id
    ?? verificationPayload?.last_completed_run_id
    ?? null
  );
}

export function filterVerificationItemsForRun(
  items: VerificationItem[] | null | undefined,
  runId: string | null,
): VerificationItem[] {
  const validItems = getValidVerificationItems(items);
  if (!runId) {
    return validItems;
  }
  return validItems.filter((item) => !item.run_id || item.run_id === runId);
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
        run_id: steps[0].run_id ?? null,
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
      run_id: step.run_id ?? null,
      label: step.phase_label ?? step.user_visible_label ?? `Step ${step.step_id}`,
      summary: step.phase_summary ?? null,
      steps: [step],
    });
  }

  return groups;
}

export function getProcessGroups(
  groupedSteps: VerificationGroup[] | null | undefined,
  steps: StepRecord[],
): Array<StepGroup | VerificationGroup> {
  if (groupedSteps && groupedSteps.length > 0) {
    return groupedSteps;
  }
  return groupStepsForDisplay(steps);
}

function getRunLabel(runId: string | null, index: number): string {
  if (!runId) {
    return index === 0 ? 'Current session' : `Session group ${index + 1}`;
  }
  const [, numericPart] = runId.split('-');
  const parsed = Number.parseInt(numericPart ?? '', 10);
  if (Number.isFinite(parsed)) {
    return `Run ${parsed}`;
  }
  return runId;
}

export function groupProcessGroupsByRun(
  groupedSteps: VerificationGroup[] | null | undefined,
  steps: StepRecord[],
): RunGroup[] {
  const groups = getProcessGroups(groupedSteps, steps);
  if (groups.length === 0) {
    return [];
  }

  const runGroups: RunGroup[] = [];
  for (const group of groups) {
    const runId = ('run_id' in group ? group.run_id : null) ?? group.steps[0]?.run_id ?? null;
    const previousRunGroup = runGroups[runGroups.length - 1];
    if (previousRunGroup && previousRunGroup.runId === runId) {
      previousRunGroup.groups.push(group);
      continue;
    }

    runGroups.push({
      id: runId ?? `session-run-${runGroups.length + 1}`,
      runId,
      label: getRunLabel(runId, runGroups.length),
      groups: [group],
    });
  }

  return runGroups;
}

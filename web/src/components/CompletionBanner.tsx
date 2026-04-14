interface CompletionBannerProps {
  status: string | undefined;
  verificationCount: number;
  waitingReason?: 'follow_up' | 'confirmation' | null;
  lastRunStatus?: 'complete' | 'stopped' | 'error' | null;
  errorMessage?: string | null;
}

export function CompletionBanner({
  status,
  verificationCount,
  waitingReason = null,
  lastRunStatus = null,
  errorMessage = null,
}: CompletionBannerProps) {
  if (!status || status === 'idle') {
    return null;
  }

  const message =
    status === 'complete'
      ? `[알림] 태스크 완료${verificationCount > 0 ? `. 확인이 필요한 항목 ${verificationCount}개.` : '.'}`
      : status === 'waiting_for_input'
        ? waitingReason === 'confirmation'
          ? '[알림] 계속 진행하려면 사용자 확인이 필요합니다.'
          : lastRunStatus === 'stopped'
            ? '[알림] 실행이 중단되었습니다. 같은 세션에서 이어서 요청할 수 있습니다.'
          : `[알림] 작업이 완료되었습니다. 같은 세션에서 이어서 요청할 수 있습니다${verificationCount > 0 ? ` (확인 필요 ${verificationCount}개)` : ''}.`
      : status === 'error'
        ? '[알림] 태스크 실행 중 오류가 발생했습니다.'
      : status === 'stopped'
          ? errorMessage ?? '[알림] 세션이 중지되었습니다.'
          : '[알림] 태스크를 진행 중입니다.';

  return <div className={`completion-banner status-${status}`} aria-live="polite">{message}</div>;
}

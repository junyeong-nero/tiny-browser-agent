interface CompletionBannerProps {
  status: string | undefined;
  verificationCount: number;
}

export function CompletionBanner({ status, verificationCount }: CompletionBannerProps) {
  if (!status || status === 'idle') {
    return null;
  }

  const message =
    status === 'complete'
      ? `[알림] 태스크 완료${verificationCount > 0 ? `. 확인이 필요한 항목 ${verificationCount}개.` : '.'}`
      : status === 'error'
        ? '[알림] 태스크 실행 중 오류가 발생했습니다.'
        : status === 'waiting_for_input'
          ? '[알림] 사용자 확인이 필요합니다.'
          : '[알림] 태스크를 진행 중입니다.';

  return <div className={`completion-banner status-${status}`}>{message}</div>;
}

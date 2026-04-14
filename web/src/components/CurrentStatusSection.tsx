import type { SessionStatus } from '../types/api';

interface CurrentStatusSectionProps {
  requestText: string | null;
  status: SessionStatus | null | undefined;
}

const STATUS_LABELS: Record<SessionStatus, string> = {
  idle: '준비됨',
  running: '진행중',
  waiting_for_input: '완료',
  complete: '완료',
  error: '완료',
  stopped: '완료',
};

export function CurrentStatusSection({
  requestText,
  status,
}: CurrentStatusSectionProps) {
  return (
    <section className="verification-section current-status-section">
      <h2>지금 상태</h2>
      <div className="status-summary-block">
        <div className="status-summary-label">요청</div>
        <p>{requestText ?? '아직 요청 내용이 없습니다.'}</p>
      </div>
      <dl className="status-facts">
        <div className="status-fact">
          <dt>상태</dt>
          <dd>{status ? STATUS_LABELS[status] : '준비됨'}</dd>
        </div>
      </dl>
    </section>
  );
}

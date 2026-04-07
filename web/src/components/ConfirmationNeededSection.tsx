import { getValidVerificationItems } from '../reviewPanel';
import type { VerificationItem } from '../types/api';

interface ConfirmationNeededSectionProps {
  items: VerificationItem[] | null | undefined;
  onSelectStepPreview: (stepId: number) => void;
}

export function ConfirmationNeededSection({
  items,
  onSelectStepPreview,
}: ConfirmationNeededSectionProps) {
  const validItems = getValidVerificationItems(items);
  if (validItems.length === 0) {
    return null;
  }

  return (
    <section className="verification-section confirmation-needed-section">
      <h2>확인 필요 항목 ({validItems.length})</h2>
      <div className="verification-items">
        {validItems.map((item) => (
          <article key={item.id} className={`verification-item status-${item.status}`}>
            <div className="verification-item-message">{item.message}</div>
            {item.detail && <div className="verification-item-detail">{item.detail}</div>}
            <button
              type="button"
              className="btn-secondary preview-button"
              onClick={() => onSelectStepPreview(item.source_step_id as number)}
            >
              이 시점 보기
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

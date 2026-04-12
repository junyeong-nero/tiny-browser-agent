import { useArtifactClient } from '../api/ArtifactClientContext';
import { getValidVerificationItems } from '../reviewPanel';
import type { VerificationItem } from '../types/api';
import { AccessibilityTreeView } from './AccessibilityTreeView';

interface ConfirmationNeededSectionProps {
  items: VerificationItem[] | null | undefined;
  onSelectStepPreview: (stepId: number) => void;
  sessionId: string | null | undefined;
}

export function ConfirmationNeededSection({
  items,
  onSelectStepPreview,
  sessionId,
}: ConfirmationNeededSectionProps) {
  const artifactClient = useArtifactClient();
  const validItems = getValidVerificationItems(items);
  if (validItems.length === 0) {
    return null;
  }

  return (
    <section className="verification-section confirmation-needed-section">
      <h2>확인 필요 항목 ({validItems.length})</h2>
      <div className="verification-items">
        {validItems.map((item) => (
          (() => {
            const htmlPath = item.html_path ?? null;
            const htmlHref = sessionId && htmlPath
              ? artifactClient.getArtifactHref(sessionId, htmlPath)
              : null;

            return (
              <article key={item.id} className={`verification-item status-${item.status}`}>
                <div className="verification-item-message">{item.message}</div>
                {item.detail && <div className="verification-item-detail">{item.detail}</div>}
                {item.ambiguity_type && (
                  <div className="verification-item-meta">Ambiguity: {item.ambiguity_type}</div>
                )}
                {item.review_evidence && item.review_evidence.length > 0 && (
                  <div className="verification-item-meta">Evidence: {item.review_evidence.join(', ')}</div>
                )}
                <button
                  type="button"
                  className="btn-secondary preview-button"
                  onClick={() => onSelectStepPreview(item.source_step_id as number)}
                >
                  이 시점 보기
                </button>
                {htmlHref && (
                  <a href={htmlHref} target="_blank" rel="noreferrer">
                    HTML
                  </a>
                )}
                {htmlPath && sessionId && !htmlHref && (
                  <button type="button" className="btn-secondary preview-button" onClick={() => void artifactClient.openArtifact(sessionId, htmlPath)}>
                    HTML
                  </button>
                )}
                <AccessibilityTreeView
                  sessionId={sessionId}
                  artifactName={item.a11y_path}
                  label={`Verification item ${item.id}`}
                />
              </article>
            );
          })()
        ))}
      </div>
    </section>
  );
}

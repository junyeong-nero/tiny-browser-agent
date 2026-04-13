import { useArtifactClient } from '../api/ArtifactClientContext';
import type { SessionSnapshot } from '../types/api';

interface ArtifactLinksProps {
  snapshot: SessionSnapshot | null;
}

export function ArtifactLinks({ snapshot }: ArtifactLinksProps) {
  const artifactClient = useArtifactClient();

  if (!snapshot) {
    return null;
  }

  const isComplete = snapshot.status === 'complete' || snapshot.status === 'stopped' || snapshot.status === 'error';
  const latestStepPrefix =
    snapshot.latest_step_id != null ? `step-${String(snapshot.latest_step_id).padStart(4, '0')}` : null;

  const renderArtifactAction = (label: string, name: string) => {
    return (
      <button type="button" className="btn-secondary preview-button" onClick={() => void artifactClient.openArtifact(snapshot.session_id, name)}>
        {label}
      </button>
    );
  };

  return (
    <div className="artifact-links">
      <h3>Artifacts</h3>
      <ul>
        {latestStepPrefix && (
          <>
            <li>
              {renderArtifactAction('Latest Screenshot', `${latestStepPrefix}.png`)}
            </li>
            <li>
              {renderArtifactAction('Latest HTML', `${latestStepPrefix}.html`)}
            </li>
            <li>
              {renderArtifactAction('Latest Metadata', `${latestStepPrefix}.json`)}
            </li>
          </>
        )}
        {isComplete && (
          <li>
            {renderArtifactAction('Session Video', 'session.webm')}
          </li>
        )}
      </ul>
    </div>
  );
}

import { SessionSnapshot } from '../types/api';

interface ArtifactLinksProps {
  snapshot: SessionSnapshot | null;
}

export function ArtifactLinks({ snapshot }: ArtifactLinksProps) {
  if (!snapshot || !snapshot.artifacts_base_url) {
    return null;
  }

  const baseUrl = snapshot.artifacts_base_url;
  const isComplete = snapshot.status === 'complete' || snapshot.status === 'stopped' || snapshot.status === 'error';

  return (
    <div className="artifact-links">
      <h3>Artifacts</h3>
      <ul>
        {snapshot.latest_step_id != null && (
          <>
            <li>
              <a href={`${baseUrl}/step-${String(snapshot.latest_step_id).padStart(4, '0')}.png`} target="_blank" rel="noreferrer">
                Latest Screenshot
              </a>
            </li>
            <li>
              <a href={`${baseUrl}/step-${String(snapshot.latest_step_id).padStart(4, '0')}.html`} target="_blank" rel="noreferrer">
                Latest HTML
              </a>
            </li>
            <li>
              <a href={`${baseUrl}/step-${String(snapshot.latest_step_id).padStart(4, '0')}.json`} target="_blank" rel="noreferrer">
                Latest Metadata
              </a>
            </li>
          </>
        )}
        {isComplete && (
          <li>
            <a href={`${baseUrl}/session.webm`} target="_blank" rel="noreferrer">
              Session Video
            </a>
          </li>
        )}
      </ul>
    </div>
  );
}

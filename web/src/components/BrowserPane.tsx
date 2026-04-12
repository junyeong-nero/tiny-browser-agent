import type { Ref } from 'react';

import { useArtifactClient } from '../api/ArtifactClientContext';
import type { StepRecord } from '../types/api';

interface BrowserPaneProps {
  currentScreenshotB64: string | null | undefined;
  currentUpdatedAt: number | null | undefined;
  selectedStep: StepRecord | null | undefined;
  sessionId: string | null | undefined;
  status: string | undefined;
  hasBrowserSurfaceBridge?: boolean;
  paneRef?: Ref<HTMLElement>;
}

export function BrowserPane({
  currentScreenshotB64,
  currentUpdatedAt,
  selectedStep,
  sessionId,
  status,
  hasBrowserSurfaceBridge = false,
  paneRef,
}: BrowserPaneProps) {
  const artifactClient = useArtifactClient();
  const stepScreenshotUrl =
    sessionId && selectedStep?.screenshot_path
      ? artifactClient.getArtifactHref(sessionId, selectedStep.screenshot_path)
      : null;
  const stepHtmlUrl =
    sessionId && selectedStep?.html_path
      ? artifactClient.getArtifactHref(sessionId, selectedStep.html_path)
      : null;
  const stepMetadataUrl =
    sessionId && selectedStep?.metadata_path
      ? artifactClient.getArtifactHref(sessionId, selectedStep.metadata_path)
      : null;
  const isStepPreview = !!selectedStep && !!stepScreenshotUrl;
  const selectedStepHtmlPath = selectedStep?.html_path ?? null;
  const selectedStepMetadataPath = selectedStep?.metadata_path ?? null;

  if (!isStepPreview && !currentScreenshotB64) {
    return (
      <section
        className="browser-pane empty"
        ref={paneRef}
        tabIndex={-1}
        aria-label="Browser surface"
        data-browser-surface-host="true"
        data-browser-surface-connected={hasBrowserSurfaceBridge ? 'true' : 'false'}
      >
        {status === 'running' ? 'Waiting for browser...' : 'No browser preview available'}
      </section>
    );
  }

  return (
    <section
      className="browser-pane"
      ref={paneRef}
      tabIndex={-1}
      aria-label="Browser surface"
      data-browser-surface-host="true"
      data-browser-surface-connected={hasBrowserSurfaceBridge ? 'true' : 'false'}
    >
      <div className="browser-pane-content">
        <div className="browser-preview-label">
          {isStepPreview ? `Step ${selectedStep.step_id} preview` : 'Current preview'}
        </div>
        <img
          src={
            isStepPreview
              ? stepScreenshotUrl
              : `data:image/png;base64,${currentScreenshotB64}`
          }
          alt={isStepPreview ? `Step ${selectedStep.step_id} browser preview` : 'Current browser preview'}
          className="browser-screenshot"
        />
        {isStepPreview && selectedStep && (
          <div className="browser-step-meta">
            Captured for step {selectedStep.step_id}
            {selectedStep.url ? ` · ${selectedStep.url}` : ''}
          </div>
        )}
        {!isStepPreview && currentUpdatedAt != null && (
          <div className="browser-updated-at">
            Updated {new Date(currentUpdatedAt * 1000).toLocaleTimeString()}
          </div>
        )}
        {isStepPreview && (stepHtmlUrl || stepMetadataUrl) && (
          <div className="browser-preview-links">
            {selectedStepHtmlPath && stepHtmlUrl && (
              <a href={stepHtmlUrl} target="_blank" rel="noreferrer">
                HTML
              </a>
            )}
            {selectedStepHtmlPath && !stepHtmlUrl && sessionId && (
              <button type="button" className="btn-secondary preview-button" onClick={() => void artifactClient.openArtifact(sessionId, selectedStepHtmlPath)}>
                HTML
              </button>
            )}
            {selectedStepMetadataPath && stepMetadataUrl && (
              <a href={stepMetadataUrl} target="_blank" rel="noreferrer">
                Metadata
              </a>
            )}
            {selectedStepMetadataPath && !stepMetadataUrl && sessionId && (
              <button type="button" className="btn-secondary preview-button" onClick={() => void artifactClient.openArtifact(sessionId, selectedStepMetadataPath)}>
                Metadata
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

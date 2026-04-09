import type { Ref } from 'react';

import { buildArtifactUrl } from '../reviewPanel';
import type { StepRecord } from '../types/api';

interface BrowserPaneProps {
  currentScreenshotB64: string | null | undefined;
  currentUpdatedAt: number | null | undefined;
  selectedStep: StepRecord | null | undefined;
  artifactsBaseUrl: string | null | undefined;
  status: string | undefined;
  paneRef?: Ref<HTMLDivElement>;
}

export function BrowserPane({
  currentScreenshotB64,
  currentUpdatedAt,
  selectedStep,
  artifactsBaseUrl,
  status,
  paneRef,
}: BrowserPaneProps) {
  const stepScreenshotUrl = buildArtifactUrl(artifactsBaseUrl, selectedStep?.screenshot_path);
  const stepHtmlUrl = buildArtifactUrl(artifactsBaseUrl, selectedStep?.html_path);
  const stepMetadataUrl = buildArtifactUrl(artifactsBaseUrl, selectedStep?.metadata_path);
  const isStepPreview = !!selectedStep && !!stepScreenshotUrl;

  if (!isStepPreview && !currentScreenshotB64) {
    return (
      <div className="browser-pane empty" ref={paneRef} tabIndex={-1}>
        {status === 'running' ? 'Waiting for browser...' : 'No browser preview available'}
      </div>
    );
  }

  return (
    <div className="browser-pane" ref={paneRef} tabIndex={-1}>
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
            {stepHtmlUrl && (
              <a href={stepHtmlUrl} target="_blank" rel="noreferrer">
                HTML
              </a>
            )}
            {stepMetadataUrl && (
              <a href={stepMetadataUrl} target="_blank" rel="noreferrer">
                Metadata
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

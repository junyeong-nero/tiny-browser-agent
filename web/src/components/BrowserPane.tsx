import { useEffect, useState, type Ref } from 'react';

import { useArtifactClient } from '../api/ArtifactClientContext';
import type { StepRecord } from '../types/api';

interface BrowserPaneProps {
  currentScreenshotB64: string | null | undefined;
  currentUpdatedAt: number | null | undefined;
  selectedStep: StepRecord | null | undefined;
  sessionId: string | null | undefined;
  status: string | undefined;
  hasBrowserSurfaceBridge?: boolean;
  isFocused?: boolean;
  paneRef?: Ref<HTMLElement>;
}

export function BrowserPane({
  currentScreenshotB64,
  currentUpdatedAt,
  selectedStep,
  sessionId,
  status,
  hasBrowserSurfaceBridge = false,
  isFocused = false,
  paneRef,
}: BrowserPaneProps) {
  const artifactClient = useArtifactClient();
  const [stepScreenshotB64, setStepScreenshotB64] = useState<string | null>(null);
  const [stepScreenshotError, setStepScreenshotError] = useState<string | null>(null);
  const [isLoadingStepScreenshot, setIsLoadingStepScreenshot] = useState(false);
  const isStepPreview = !!selectedStep;
  const selectedStepHtmlPath = selectedStep?.html_path ?? null;
  const selectedStepMetadataPath = selectedStep?.metadata_path ?? null;
  const currentPreviewSrc = currentScreenshotB64 ? `data:image/png;base64,${currentScreenshotB64}` : null;
  const stepPreviewSrc = stepScreenshotB64 ? `data:image/png;base64,${stepScreenshotB64}` : null;

  useEffect(() => {
    let cancelled = false;

    if (!sessionId || !selectedStep?.screenshot_path) {
      setStepScreenshotB64(null);
      setStepScreenshotError(null);
      setIsLoadingStepScreenshot(false);
      return () => {
        cancelled = true;
      };
    }

    setStepScreenshotB64(null);
    setStepScreenshotError(null);
    setIsLoadingStepScreenshot(true);

    void artifactClient
      .readArtifactBinary(sessionId, selectedStep.screenshot_path)
      .then((artifactPayload) => {
        if (cancelled) {
          return;
        }
        setStepScreenshotB64(artifactPayload);
        setStepScreenshotError(null);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setStepScreenshotError(error instanceof Error ? error.message : 'Failed to load preview');
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingStepScreenshot(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [artifactClient, selectedStep?.screenshot_path, sessionId]);

  if (!isStepPreview && !currentPreviewSrc && !hasBrowserSurfaceBridge) {
    return (
      <section
        className="browser-pane empty"
        tabIndex={-1}
        aria-label="Browser surface"
        data-browser-surface-host="true"
        data-browser-surface-connected={hasBrowserSurfaceBridge ? 'true' : 'false'}
        data-focus-active={isFocused ? 'true' : 'false'}
      >
        {status === 'running' ? 'Waiting for browser...' : 'No browser preview available'}
      </section>
    );
  }

  return (
    <section
      className="browser-pane"
      tabIndex={-1}
      aria-label="Browser surface"
      data-browser-surface-host="true"
      data-browser-surface-connected={hasBrowserSurfaceBridge ? 'true' : 'false'}
      data-focus-active={isFocused ? 'true' : 'false'}
    >
      <div className="browser-pane-content">
        <div className="browser-preview-label">
          {isStepPreview ? `Inspection mode · Step ${selectedStep?.step_id}` : 'Live browser surface'}
        </div>
        {!isStepPreview && (
          <>
            <div ref={paneRef} className="browser-surface-host" data-browser-surface-live={hasBrowserSurfaceBridge ? 'true' : 'false'} />
            {hasBrowserSurfaceBridge ? (
              <div className="browser-step-meta">Live surface connected through the desktop bridge.</div>
            ) : currentPreviewSrc ? (
              <>
                <img
                  src={currentPreviewSrc}
                  alt="Current browser preview"
                  className="browser-screenshot"
                />
                <div className="browser-step-meta">Live surface unavailable. Showing screenshot fallback.</div>
              </>
            ) : (
              <div className="browser-step-meta">
                {status === 'running' ? 'Waiting for browser...' : 'No browser preview available'}
              </div>
            )}
            {currentUpdatedAt != null && currentPreviewSrc && (
              <div className="browser-updated-at">
                Updated {new Date(currentUpdatedAt * 1000).toLocaleTimeString()}
              </div>
            )}
          </>
        )}
        {isStepPreview && selectedStep && (
          <>
            {stepPreviewSrc && (
              <img
                src={stepPreviewSrc}
                alt={`Step ${selectedStep.step_id} browser preview`}
                className="browser-screenshot"
              />
            )}
            {isLoadingStepScreenshot && <div className="browser-step-meta">Loading historical preview...</div>}
            {stepScreenshotError && <div className="browser-step-meta">{stepScreenshotError}</div>}
            <div className="browser-step-meta">
              Captured for step {selectedStep.step_id}
              {selectedStep.url ? ` · ${selectedStep.url}` : ''}
            </div>
            {(selectedStepHtmlPath || selectedStepMetadataPath) && sessionId && (
              <div className="browser-preview-links">
                {selectedStepHtmlPath && (
                  <button type="button" className="btn-secondary preview-button" onClick={() => void artifactClient.openArtifact(sessionId, selectedStepHtmlPath)}>
                    HTML
                  </button>
                )}
                {selectedStepMetadataPath && (
                  <button type="button" className="btn-secondary preview-button" onClick={() => void artifactClient.openArtifact(sessionId, selectedStepMetadataPath)}>
                    Metadata
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

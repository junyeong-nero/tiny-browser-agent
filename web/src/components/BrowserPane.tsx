import { useEffect, useRef, useState, type Ref } from 'react';

import { useArtifactClient } from '../api/ArtifactClientContext';
import type { StepRecord } from '../types/api';

interface BrowserPaneProps {
  currentScreenshotB64: string | null | undefined;
  selectedStep: StepRecord | null | undefined;
  sessionId: string | null | undefined;
  status: string | undefined;
  hasBrowserSurfaceBridge?: boolean;
  isFocused?: boolean;
  paneRef?: Ref<HTMLElement>;
}

export function BrowserPane({
  currentScreenshotB64,
  selectedStep,
  sessionId,
  status,
  hasBrowserSurfaceBridge = false,
  isFocused = false,
  paneRef,
}: BrowserPaneProps) {
  const artifactClient = useArtifactClient();
  const internalPaneRef = useRef<HTMLElement | null>(null);
  const [stepScreenshotB64, setStepScreenshotB64] = useState<string | null>(null);
  const [stepScreenshotError, setStepScreenshotError] = useState<string | null>(null);
  const [isLoadingStepScreenshot, setIsLoadingStepScreenshot] = useState(false);
  const isStepPreview = !!selectedStep;
  const selectedStepHtmlPath = selectedStep?.html_path ?? null;
  const selectedStepMetadataPath = selectedStep?.metadata_path ?? null;
  const snapshotPreviewSrc = currentScreenshotB64 ? `data:image/png;base64,${currentScreenshotB64}` : null;
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

  const assignPaneRef = (node: HTMLElement | null) => {
    internalPaneRef.current = node;
    if (typeof paneRef === 'function') {
      paneRef(node);
    } else if (paneRef) {
      (paneRef as { current: HTMLElement | null }).current = node;
    }
  };

  if (!isStepPreview && !snapshotPreviewSrc) {
    return (
      <section
        ref={assignPaneRef}
        className="browser-pane empty"
        tabIndex={-1}
        role="region"
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
      ref={assignPaneRef}
      className="browser-pane"
      tabIndex={-1}
      role="region"
      aria-label="Browser surface"
      data-browser-surface-host="true"
      data-browser-surface-connected={hasBrowserSurfaceBridge ? 'true' : 'false'}
      data-focus-active={isFocused ? 'true' : 'false'}
    >
      <div className="browser-pane-content">
        {isStepPreview && (
          <div className="browser-preview-label">
            {`Inspection mode · Step ${selectedStep?.step_id}`}
          </div>
        )}
        {!isStepPreview && snapshotPreviewSrc && (
          <img
            src={snapshotPreviewSrc}
            alt="Current browser preview"
            className="browser-screenshot browser-screenshot-fixed"
          />
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

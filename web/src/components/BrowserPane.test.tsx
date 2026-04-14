import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ArtifactClientProvider } from '../api/ArtifactClientContext';
import { httpArtifactClient } from '../api/httpArtifactClient';
import { BrowserPane } from './BrowserPane';

describe('BrowserPane', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('renders the current preview when no step is selected', () => {
    render(
      <ArtifactClientProvider client={httpArtifactClient}>
        <BrowserPane
          currentScreenshotB64="Zm9v"
          selectedStep={null}
          sessionId="ses_test"
          status="complete"
        />
      </ArtifactClientProvider>,
    );

    expect(screen.getByLabelText('Browser surface')).toHaveAttribute(
      'data-browser-surface-connected',
      'false',
    );
    expect(screen.getByAltText('Current browser preview')).toHaveAttribute(
      'src',
      'data:image/png;base64,Zm9v',
    );
    expect(screen.getByText('Live surface unavailable. Showing screenshot fallback.')).toBeInTheDocument();
    expect(screen.queryByText('Live browser surface')).not.toBeInTheDocument();
    expect(screen.queryByText(/Updated /)).not.toBeInTheDocument();
  });

  it('renders the selected step preview from artifact bytes and open actions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, arrayBuffer: async () => new Uint8Array([65, 66]).buffer }),
    );

    render(
      <ArtifactClientProvider client={httpArtifactClient}>
        <BrowserPane
          currentScreenshotB64="Zm9v"
          sessionId="ses_test"
          selectedStep={{
            step_id: 12,
            timestamp: 1700000001,
            reasoning: 'Clicked the button',
            function_calls: [],
            url: 'https://example.com/seat',
            status: 'complete',
            screenshot_path: 'step-0012.png',
            html_path: 'step-0012.html',
            metadata_path: 'step-0012.json',
            error_message: null,
            phase_id: 'phase-1',
            phase_label: '탐색',
            phase_summary: '페이지를 탐색했습니다.',
            user_visible_label: '좌석 선택',
          }}
          status="complete"
          hasBrowserSurfaceBridge
        />
      </ArtifactClientProvider>,
    );

    expect(screen.getByText('Inspection mode · Step 12')).toBeInTheDocument();
    expect(screen.getByLabelText('Browser surface')).toHaveAttribute(
      'data-browser-surface-connected',
      'true',
    );
    expect(screen.queryByText('Live surface connected through the desktop bridge.')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByAltText('Step 12 browser preview')).toHaveAttribute(
        'src',
        'data:image/png;base64,QUI=',
      );
    });

    expect(screen.getByRole('button', { name: 'HTML' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Metadata' })).toBeInTheDocument();
  });
});

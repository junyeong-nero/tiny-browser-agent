import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BrowserPane } from './BrowserPane';

describe('BrowserPane', () => {
  it('renders the current preview when no step is selected', () => {
    render(
      <BrowserPane
        currentScreenshotB64="Zm9v"
        currentUpdatedAt={1700000000}
        selectedStep={null}
        sessionId="ses_test"
        status="complete"
      />,
    );

    expect(screen.getByText('Current preview')).toBeInTheDocument();
    expect(screen.getByLabelText('Browser surface')).toHaveAttribute(
      'data-browser-surface-connected',
      'false',
    );
    expect(screen.getByAltText('Current browser preview')).toHaveAttribute(
      'src',
      'data:image/png;base64,Zm9v',
    );
  });

  it('renders the selected step preview and artifact links', () => {
    render(
      <BrowserPane
        currentScreenshotB64="Zm9v"
        currentUpdatedAt={1700000000}
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
      />,
    );

    expect(screen.getByText('Step 12 preview')).toBeInTheDocument();
    expect(screen.getByLabelText('Browser surface')).toHaveAttribute(
      'data-browser-surface-connected',
      'true',
    );
    expect(screen.getByAltText('Step 12 browser preview')).toHaveAttribute(
      'src',
      '/api/sessions/ses_test/artifacts/step-0012.png',
    );
    expect(screen.getByRole('link', { name: 'HTML' })).toHaveAttribute(
      'href',
      '/api/sessions/ses_test/artifacts/step-0012.html',
    );
    expect(screen.getByRole('link', { name: 'Metadata' })).toHaveAttribute(
      'href',
      '/api/sessions/ses_test/artifacts/step-0012.json',
    );
  });
});

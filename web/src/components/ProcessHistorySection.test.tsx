import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ArtifactClientProvider } from '../api/ArtifactClientContext';
import { httpArtifactClient } from '../api/httpArtifactClient';
import { ProcessHistorySection } from './ProcessHistorySection';

describe('ProcessHistorySection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders a single disclosure without phase metadata', () => {
    render(
      <ArtifactClientProvider client={httpArtifactClient}>
        <ProcessHistorySection
          sessionId="ses_test"
          steps={[
            {
              step_id: 1,
              timestamp: 1,
              reasoning: 'Opened the site',
              function_calls: [],
              url: null,
              status: 'complete',
              screenshot_path: null,
              html_path: null,
              metadata_path: null,
              error_message: null,
            },
          ]}
          previewMode={{ kind: 'current' }}
          onSelectStepPreview={vi.fn()}
        />
      </ArtifactClientProvider>,
    );

    expect(screen.getByText('전체 과정 보기')).toBeInTheDocument();
    expect(screen.getByText('Opened the site')).toBeInTheDocument();
  });

  it('preserves backend phase order and handles step preview actions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, text: async () => '- link "Result"' }),
    );
    const onSelectStepPreview = vi.fn();

    render(
      <ArtifactClientProvider client={httpArtifactClient}>
        <ProcessHistorySection
          sessionId="ses_test"
          steps={[
            {
              step_id: 2,
              timestamp: 2,
              reasoning: 'Selected a flight',
              function_calls: [{ name: 'click_at', args: {} }],
              url: 'https://example.com/flight',
              status: 'complete',
              screenshot_path: 'step-0002.png',
              html_path: 'step-0002.html',
              metadata_path: 'step-0002.json',
              a11y_path: 'step-0002.a11y.yaml',
              ambiguity_message: '검토가 필요한 선택입니다.',
              review_evidence: ['repeated_click_pattern'],
              error_message: null,
              phase_id: 'phase-search',
              phase_label: '항공편 탐색',
              phase_summary: '검색 결과를 살펴봤습니다.',
              user_visible_label: '항공편 선택',
            },
            {
              step_id: 3,
              timestamp: 3,
              reasoning: 'Reviewed the fare',
              function_calls: [],
              url: 'https://example.com/fare',
              status: 'complete',
              screenshot_path: 'step-0003.png',
              html_path: null,
              metadata_path: null,
              error_message: null,
              phase_id: 'phase-review',
              phase_label: '요금 검토',
              phase_summary: '가격 조건을 검토했습니다.',
              user_visible_label: '요금 검토',
            },
          ]}
          previewMode={{ kind: 'step', stepId: 2 }}
          onSelectStepPreview={onSelectStepPreview}
        />
      </ArtifactClientProvider>,
    );

    const summaries = screen.getAllByText(/항공편 탐색|요금 검토/);
    expect(summaries[0]).toHaveTextContent('항공편 탐색');
    expect(summaries[1]).toHaveTextContent('요금 검토');
    
    fireEvent.click(screen.getAllByRole('button', { name: '이 시점 보기' })[0]);
    expect(onSelectStepPreview).toHaveBeenCalledWith(2);
    fireEvent.click(screen.getByRole('button', { name: 'A11y 보기' }));
    expect(screen.getByText('검토가 필요한 선택입니다.')).toBeInTheDocument();
    expect(await screen.findByText('- link "Result"')).toBeInTheDocument();
  });
});

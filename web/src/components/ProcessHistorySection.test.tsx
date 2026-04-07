import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ProcessHistorySection } from './ProcessHistorySection';

describe('ProcessHistorySection', () => {
  it('renders a single disclosure without phase metadata', () => {
    render(
      <ProcessHistorySection
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
        artifactsBaseUrl="/api/sessions/ses_test/artifacts"
      />,
    );

    expect(screen.getByText('전체 과정 보기')).toBeInTheDocument();
    expect(screen.getByText('Opened the site')).toBeInTheDocument();
  });

  it('preserves backend phase order and handles step preview actions', () => {
    const onSelectStepPreview = vi.fn();

    render(
      <ProcessHistorySection
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
        artifactsBaseUrl="/api/sessions/ses_test/artifacts"
      />,
    );

    const summaries = screen.getAllByText(/항공편 탐색|요금 검토/);
    expect(summaries[0]).toHaveTextContent('항공편 탐색');
    expect(summaries[1]).toHaveTextContent('요금 검토');

    fireEvent.click(screen.getAllByRole('button', { name: '이 시점 보기' })[0]);
    expect(onSelectStepPreview).toHaveBeenCalledWith(2);
  });
});

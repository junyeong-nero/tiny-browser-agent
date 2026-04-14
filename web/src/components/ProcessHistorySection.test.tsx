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
    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.getByText('Opened the site')).toBeInTheDocument();
  });

  it('foregrounds summarized reason text and tucks raw reasoning behind a disclosure', async () => {
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
              run_id: 'run-0001',
              timestamp: 2,
              reasoning: '검색 결과를 검토한 뒤 원하는 항공편 카드의 CTA를 클릭했습니다.',
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
              action_summary: '항공편 선택',
              reason: '원하는 항공편 상세 정보로 이동하기 위해 선택했습니다.',
              summary_source: 'openrouter',
              user_visible_label: '항공편 선택',
            },
            {
              step_id: 3,
              run_id: 'run-0001',
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
              action_summary: '요금 검토',
              reason: '선택한 항공편의 가격 조건을 확인했습니다.',
              summary_source: 'openrouter',
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
    expect(screen.getByText('항공편 선택')).toBeInTheDocument();
    expect(screen.getAllByText('OpenRouter 요약')).toHaveLength(2);
    expect(screen.getByText('원하는 항공편 상세 정보로 이동하기 위해 선택했습니다.')).toBeInTheDocument();
    expect(screen.getByText('선택한 항공편의 가격 조건을 확인했습니다.')).toBeInTheDocument();
    fireEvent.click(screen.getAllByText('원문 reasoning 보기')[0]);
    expect(
      screen.getByText('검색 결과를 검토한 뒤 원하는 항공편 카드의 CTA를 클릭했습니다.'),
    ).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: '이 시점 보기' })[0]);
    expect(onSelectStepPreview).toHaveBeenCalledWith(2);
    fireEvent.click(screen.getByRole('button', { name: 'A11y 보기' }));
    expect(screen.getByText('검토가 필요한 선택입니다.')).toBeInTheDocument();
    expect(await screen.findByText('- link "Result"')).toBeInTheDocument();
  });

  it('groups backend process history by run id', () => {
    render(
      <ArtifactClientProvider client={httpArtifactClient}>
        <ProcessHistorySection
          sessionId="ses_test"
          groupedSteps={[
            {
              id: 'run-0001:phase-search',
              run_id: 'run-0001',
              label: '검색',
              summary: '첫 번째 실행',
              step_ids: [1],
              steps: [
                {
                  step_id: 1,
                  run_id: 'run-0001',
                  timestamp: 1,
                  reasoning: '첫 번째 실행',
                  function_calls: [],
                  url: null,
                  status: 'complete',
                  screenshot_path: null,
                  html_path: null,
                  metadata_path: null,
                  error_message: null,
                  action_summary: null,
                  reason: null,
                  summary_source: null,
                },
              ],
            },
            {
              id: 'run-0002:phase-search',
              run_id: 'run-0002',
              label: '후속 검색',
              summary: '두 번째 실행',
              step_ids: [2],
              steps: [
                {
                  step_id: 2,
                  run_id: 'run-0002',
                  timestamp: 2,
                  reasoning: '두 번째 실행',
                  function_calls: [],
                  url: null,
                  status: 'complete',
                  screenshot_path: null,
                  html_path: null,
                  metadata_path: null,
                  error_message: null,
                  action_summary: null,
                  reason: null,
                  summary_source: null,
                },
              ],
            },
          ]}
          steps={[]}
          previewMode={{ kind: 'current' }}
          onSelectStepPreview={vi.fn()}
        />
      </ArtifactClientProvider>,
    );

    expect(screen.getByText('Run 1')).toBeInTheDocument();
    expect(screen.getByText('Run 2')).toBeInTheDocument();
    expect(screen.getAllByText('첫 번째 실행')).toHaveLength(2);
    expect(screen.getAllByText('두 번째 실행')).toHaveLength(2);
  });
});

import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ArtifactClientProvider } from '../api/ArtifactClientContext';
import { httpArtifactClient } from '../api/httpArtifactClient';
import { ProcessHistorySection } from './ProcessHistorySection';

describe('ProcessHistorySection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('derives a readable fallback summary and reason for the latest action while metadata is pending', () => {
    render(
      <ArtifactClientProvider client={httpArtifactClient}>
        <ProcessHistorySection
          sessionId="ses_test"
          steps={[
            {
              step_id: 1,
              timestamp: 1,
              reasoning: null,
              function_calls: [{ name: 'type_text_at', args: { text: 'Naver' } }],
              url: null,
              status: 'running',
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

    const recentSection = screen.getByText('최근 행동').closest('section')!;
    expect(screen.getByText('최근 행동')).toBeInTheDocument();
    expect(within(recentSection).getByText('Step 1')).toBeInTheDocument();
    expect(within(recentSection).getByText('행동 요약')).toBeInTheDocument();
    expect(within(recentSection).getByText('"Naver" 입력')).toBeInTheDocument();
    expect(within(recentSection).getByText('이유')).toBeInTheDocument();
    expect(within(recentSection).getByText('필요한 텍스트를 입력하는 단계입니다.')).toBeInTheDocument();
    expect(screen.getByText('이전 과정 보기')).toBeInTheDocument();
    fireEvent.click(screen.getByText('이전 과정 보기'));
    expect(screen.getByText('이전 과정이 없습니다.')).toBeInTheDocument();
  });

  it('foregrounds the latest action and tucks secondary details behind disclosures', async () => {
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

    const recentSection = screen.getByText('최근 행동').closest('section')!;
    expect(screen.getByText('최근 행동')).toBeInTheDocument();
    expect(within(recentSection).getByText('행동 요약')).toBeInTheDocument();
    expect(within(recentSection).getByText('요금 검토')).toBeInTheDocument();
    expect(within(recentSection).getByText('이유')).toBeInTheDocument();
    expect(within(recentSection).getByText('선택한 항공편의 가격 조건을 확인했습니다.')).toBeInTheDocument();
    expect(screen.queryByText('항공편 선택')).not.toBeInTheDocument();
    expect(screen.queryByText('검색 결과를 검토한 뒤 원하는 항공편 카드의 CTA를 클릭했습니다.')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('세부 정보 보기'));
    expect(screen.getByText('Reviewed the fare')).toBeInTheDocument();

    fireEvent.click(screen.getByText('이전 과정 보기'));
    expect(screen.getByText('원하는 항공편 상세 정보로 이동하기 위해 선택했습니다.')).toBeInTheDocument();
    expect(screen.getAllByText('항공편 선택')).toHaveLength(2);

    fireEvent.click(screen.getByRole('button', { name: '세부 정보 보기' }));
    expect(
      screen.getByText('검색 결과를 검토한 뒤 원하는 항공편 카드의 CTA를 클릭했습니다.'),
    ).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: '이 시점 보기' })[1]);
    expect(onSelectStepPreview).toHaveBeenCalledWith(2);
    fireEvent.click(screen.getByRole('button', { name: 'A11y 보기' }));
    expect(screen.getByText('검토가 필요한 선택입니다.')).toBeInTheDocument();
    expect(await screen.findByText('- link "Result"')).toBeInTheDocument();
  });

  it('keeps showing the last ready action until the new running step has summary metadata', () => {
    render(
      <ArtifactClientProvider client={httpArtifactClient}>
        <ProcessHistorySection
          sessionId="ses_test"
          steps={[
            {
              step_id: 12,
              timestamp: 12,
              reasoning: '검색 결과의 첫 번째 항목을 눌렀습니다.',
              function_calls: [{ name: 'click_at', args: { x: 100, y: 200 } }],
              url: 'https://example.com/results',
              status: 'complete',
              screenshot_path: 'step-0012.png',
              html_path: null,
              metadata_path: null,
              error_message: null,
              action_summary: '검색 결과 클릭',
              reason: '원하는 결과 페이지로 이동하기 위해 선택했습니다.',
              user_visible_label: '검색 결과 클릭',
            },
            {
              step_id: 13,
              timestamp: 13,
              reasoning: null,
              function_calls: [],
              url: 'https://example.com/results',
              status: 'running',
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

    const recentSection = screen.getByText('최근 행동').closest('section')!;
    expect(within(recentSection).getByText('검색 결과 클릭')).toBeInTheDocument();
    expect(within(recentSection).getByText('원하는 결과 페이지로 이동하기 위해 선택했습니다.')).toBeInTheDocument();
    expect(within(recentSection).queryByText('Step 13')).not.toBeInTheDocument();
  });

  it('keeps older run history behind a disclosure and labels multiple runs', () => {
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

    expect(screen.getAllByText('Step 2')).toHaveLength(2);
    expect(screen.getByText('행동 요약')).toBeInTheDocument();
    expect(screen.queryByText('Run 1')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('이전 과정 보기'));
    expect(screen.getByText('Run 1')).toBeInTheDocument();
    expect(screen.getByText('검색')).toBeInTheDocument();
    expect(screen.getByText('Step 1')).toBeInTheDocument();
  });
});

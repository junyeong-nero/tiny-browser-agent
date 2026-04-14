import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { VerificationSidebar } from './VerificationSidebar';

describe('VerificationSidebar', () => {
  it('renders current-data sections and routes preview actions', () => {
    const onSelectStepPreview = vi.fn();

    render(
      <VerificationSidebar
        snapshot={{
          session_id: 'ses_test',
          status: 'complete',
          current_url: 'https://example.com',
          latest_screenshot_b64: 'Zm9v',
          latest_step_id: 2,
          last_reasoning: '마지막 요약',
          last_actions: [],
          messages: [
            { id: 'm1', role: 'user', text: '서울에서 도쿄 가는 항공권 찾아줘', timestamp: 1 },
          ],
          final_reasoning: '항공편을 찾고 가격을 정리했습니다.',
          request_text: null,
          run_summary: null,
          verification_items: [],
          final_result_summary: null,
          error_message: null,
          updated_at: 2,
        }}
        steps={[
          {
            step_id: 1,
            timestamp: 1,
            reasoning: '검색 페이지를 열었습니다.',
            function_calls: [{ name: 'navigate', args: {} }],
            url: 'https://example.com/search',
            status: 'complete',
            screenshot_path: 'step-0001.png',
            html_path: 'step-0001.html',
            metadata_path: 'step-0001.json',
            error_message: null,
          },
        ]}
        error={null}
        previewMode={{ kind: 'current' }}
        verificationPayload={null}
        onSelectStepPreview={onSelectStepPreview}
      />,
    );

    expect(screen.getByText('[알림] 태스크 완료.')).toBeInTheDocument();
    expect(screen.getByText('지금 상태')).toBeInTheDocument();
    expect(screen.getByText('최근 행동')).toBeInTheDocument();
    expect(screen.getByText('이전 과정 보기')).toBeInTheDocument();
    expect(screen.queryByText('최종 결과')).not.toBeInTheDocument();
    expect(screen.getByText('요청')).toBeInTheDocument();
    expect(screen.getByText('상태')).toBeInTheDocument();
    expect(screen.getByText('서울에서 도쿄 가는 항공권 찾아줘')).toBeInTheDocument();
    expect(screen.queryByText('요약')).not.toBeInTheDocument();
    expect(screen.queryByText('항공편을 찾고 가격을 정리했습니다.')).not.toBeInTheDocument();
    expect(screen.queryByText('과정 기록')).not.toBeInTheDocument();
    expect(screen.queryByText('Debug Artifacts')).not.toBeInTheDocument();
    expect(screen.queryByText('패널 이동')).not.toBeInTheDocument();
    expect(screen.queryByText('세부 자료')).not.toBeInTheDocument();
    expect(screen.queryByText('최근 단계')).not.toBeInTheDocument();
    expect(screen.queryByText('현재 위치')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '이 시점 보기' }));
    expect(onSelectStepPreview).toHaveBeenCalledWith(1);
  });

  it('surfaces reusable waiting state after an interrupt', () => {
    render(
      <VerificationSidebar
        snapshot={{
          session_id: 'ses_test',
          status: 'waiting_for_input',
          waiting_reason: 'follow_up',
          last_run_status: 'stopped',
          expires_at: Date.now() / 1000 + 60,
          current_url: 'https://example.com',
          latest_screenshot_b64: 'Zm9v',
          latest_step_id: 2,
          last_reasoning: '중단 직전 상태',
          last_actions: [],
          messages: [],
          final_reasoning: null,
          request_text: '테스트',
          run_summary: '중단 직전 상태',
          verification_items: [],
          final_result_summary: null,
          error_message: null,
          updated_at: 2,
        }}
        steps={[]}
        error={null}
        previewMode={{ kind: 'current' }}
        verificationPayload={null}
        onSelectStepPreview={vi.fn()}
      />,
    );

    expect(screen.getByText('[알림] 실행이 중단되었습니다. 같은 세션에서 이어서 요청할 수 있습니다.')).toBeInTheDocument();
  });
});

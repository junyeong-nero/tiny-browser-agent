import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { VerificationSidebar } from './VerificationSidebar';

describe('VerificationSidebar', () => {
  it('renders current-data sections and routes preview actions', () => {
    const onSelectCurrentPreview = vi.fn();
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
          artifacts_base_url: '/api/sessions/ses_test/artifacts',
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
        onFocusBrowserPane={vi.fn()}
        onFocusChatInput={vi.fn()}
        onFocusVerificationPanel={vi.fn()}
        onSelectCurrentPreview={onSelectCurrentPreview}
        onSelectStepPreview={onSelectStepPreview}
      />,
    );

    expect(screen.getByText('[알림] 태스크 완료.')).toBeInTheDocument();
    expect(screen.getByText('서울에서 도쿄 가는 항공권 찾아줘')).toBeInTheDocument();
    expect(screen.getAllByText('항공편을 찾고 가격을 정리했습니다.')).toHaveLength(2);
    expect(screen.getByText('과정 기록')).toBeInTheDocument();
    expect(screen.getByText('Debug Artifacts')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '이 시점 보기' }));
    expect(onSelectStepPreview).toHaveBeenCalledWith(1);

    fireEvent.click(screen.getByRole('button', { name: '현재 시점 보기' }));
    expect(onSelectCurrentPreview).toHaveBeenCalledTimes(1);
  });
});

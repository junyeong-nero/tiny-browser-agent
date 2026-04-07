import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ConfirmationNeededSection } from './ConfirmationNeededSection';

describe('ConfirmationNeededSection', () => {
  it('renders only valid verification items and triggers preview selection', () => {
    const onSelectStepPreview = vi.fn();

    render(
      <ConfirmationNeededSection
        items={[
          {
            id: 'item-1',
            message: '좌석 등급을 지정하지 않아 이코노미를 선택했습니다.',
            detail: '사용자 입력이 없어서 기본값을 사용했습니다.',
            source_step_id: 4,
            source_url: 'https://example.com/seat',
            screenshot_path: 'step-0004.png',
            html_path: 'step-0004.html',
            metadata_path: 'step-0004.json',
            status: 'needs_review',
          },
          {
            id: 'item-2',
            message: 'invalid',
            detail: null,
            source_step_id: null,
            status: 'needs_review',
          },
        ]}
        onSelectStepPreview={onSelectStepPreview}
      />,
    );

    expect(screen.getByText('확인 필요 항목 (1)')).toBeInTheDocument();
    expect(screen.queryByText('invalid')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '이 시점 보기' }));
    expect(onSelectStepPreview).toHaveBeenCalledWith(4);
  });
});

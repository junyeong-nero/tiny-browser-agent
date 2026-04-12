import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AccessibilityTreeView } from './AccessibilityTreeView';

describe('AccessibilityTreeView', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads and renders a raw accessibility tree when opened', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, text: async () => '- heading "Search"' }),
    );

    render(
      <AccessibilityTreeView
        sessionId="ses_test"
        artifactName="step-0001.a11y.yaml"
        label="Step 1"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'A11y 보기' }));

    expect(await screen.findByText('- heading "Search"')).toBeInTheDocument();
  });
});

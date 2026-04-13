import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ArtifactClientProvider } from '../api/ArtifactClientContext';
import { httpArtifactClient } from '../api/httpArtifactClient';
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
      <ArtifactClientProvider client={httpArtifactClient}>
        <AccessibilityTreeView
          sessionId="ses_test"
          artifactName="step-0001.a11y.yaml"
          label="Step 1"
        />
      </ArtifactClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'A11y 보기' }));

    expect(await screen.findByText('- heading "Search"')).toBeInTheDocument();
  });
});

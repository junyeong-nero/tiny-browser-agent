import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ArtifactClientProvider, useArtifactClient } from './ArtifactClientContext';
import { clearDesktopBridge, clearDesktopHost, installDesktopBridge, markDesktopHost } from './desktopBridge';
import { httpArtifactClient } from './httpArtifactClient';

function ArtifactClientProbe() {
  const artifactClient = useArtifactClient();
  const [error, setError] = useState<string | null>(null);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          void artifactClient
            .readArtifactText('ses_test', 'step-0001.a11y.yaml')
            .catch((artifactError) => {
              setError(
                artifactError instanceof Error ? artifactError.message : 'Failed to read artifact',
              );
            });
        }}
      >
        Read artifact
      </button>
      {error && <div>{error}</div>}
    </>
  );
}

describe('ArtifactClientProvider', () => {
  afterEach(() => {
    clearDesktopBridge();
    clearDesktopHost();
    vi.restoreAllMocks();
  });

  it('uses the HTTP artifact client when no desktop bridge is available', async () => {
    const httpReadSpy = vi.spyOn(httpArtifactClient, 'readArtifactText').mockResolvedValue('http-artifact');

    render(
      <ArtifactClientProvider>
        <ArtifactClientProbe />
      </ArtifactClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Read artifact' }));

    await waitFor(() => {
      expect(httpReadSpy).toHaveBeenCalledWith('ses_test', 'step-0001.a11y.yaml');
    });
  });

  it('uses a desktop artifact bridge installed after initial render', async () => {
    const httpReadSpy = vi.spyOn(httpArtifactClient, 'readArtifactText');
    const desktopReadSpy = vi.fn().mockResolvedValue('desktop-artifact');

    render(
      <ArtifactClientProvider>
        <ArtifactClientProbe />
      </ArtifactClientProvider>,
    );

    installDesktopBridge({
      sessions: {
        createSession: vi.fn(),
        startSession: vi.fn(),
        stopSession: vi.fn(),
        interruptSession: vi.fn(),
        closeSession: vi.fn(),
        sendMessage: vi.fn(),
        getSession: vi.fn(),
        getSteps: vi.fn(),
        getVerification: vi.fn(),
      },
      artifacts: {
        open: vi.fn().mockResolvedValue(undefined),
        readBinary: vi.fn().mockResolvedValue(''),
        readText: desktopReadSpy,
      },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Read artifact' }));

    await waitFor(() => {
      expect(desktopReadSpy).toHaveBeenCalledWith('ses_test', 'step-0001.a11y.yaml');
    });
    expect(httpReadSpy).not.toHaveBeenCalled();
  });

  it('does not fall back to HTTP artifacts when running in a desktop host without a bridge', async () => {
    const httpReadSpy = vi.spyOn(httpArtifactClient, 'readArtifactText');
    markDesktopHost();

    render(
      <ArtifactClientProvider>
        <ArtifactClientProbe />
      </ArtifactClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Read artifact' }));

    await waitFor(() => {
      expect(screen.getByText(/Desktop bridge unavailable\./i)).toBeInTheDocument();
    });

    expect(httpReadSpy).not.toHaveBeenCalled();
  });
});

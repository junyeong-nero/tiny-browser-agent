import type { BrowserSurfaceBounds, DesktopBridge } from './desktopBridge';
import type { ArtifactClient } from './artifactClient';
import type { SessionClient } from './sessionClient';
import { unsupportedArtifactClient } from './unsupportedArtifactClient';
import { unsupportedSessionClient } from './unsupportedSessionClient';


export interface StubDesktopBridgeOptions {
  onBrowserSurfaceFocus?: () => void;
  onBrowserSurfaceBounds?: (bounds: BrowserSurfaceBounds) => void;
  sessionClient?: SessionClient;
  artifactClient?: ArtifactClient;
}

export function createStubDesktopBridge(options: StubDesktopBridgeOptions = {}): DesktopBridge {
  const sessionClient = options.sessionClient ?? unsupportedSessionClient;
  const artifactClient = options.artifactClient ?? unsupportedArtifactClient;

  return {
    sessions: {
      createSession: () => sessionClient.createSession(),
      startSession: (sessionId, query) => sessionClient.startSession(sessionId, { query }),
      stopSession: (sessionId) => sessionClient.stopSession(sessionId),
      sendMessage: (sessionId, text) => sessionClient.sendMessage(sessionId, { text }),
      getSession: (sessionId) => sessionClient.getSession(sessionId),
      getSteps: (sessionId, afterStepId) => sessionClient.getSteps(sessionId, afterStepId),
      getVerification: (sessionId) => sessionClient.getVerification(sessionId),
    },
    artifacts: {
      readText: (sessionId, name) => artifactClient.readArtifactText(sessionId, name),
      readBinary: (sessionId, name) => artifactClient.readArtifactBinary(sessionId, name),
      open: (sessionId, name) => artifactClient.openArtifact(sessionId, name),
    },
    browserSurface: {
      focus() {
        options.onBrowserSurfaceFocus?.();
      },
      setBounds(bounds) {
        options.onBrowserSurfaceBounds?.(bounds);
      },
    },
  };
}

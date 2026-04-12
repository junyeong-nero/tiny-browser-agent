import { httpSessionClient } from './httpSessionClient';
import { httpArtifactClient } from './httpArtifactClient';
import type { BrowserSurfaceBounds, DesktopBridge } from './desktopBridge';


export interface StubDesktopBridgeOptions {
  onBrowserSurfaceFocus?: () => void;
  onBrowserSurfaceBounds?: (bounds: BrowserSurfaceBounds) => void;
}


function encodeBase64(data: ArrayBuffer): string {
  let binary = '';
  const bytes = new Uint8Array(data);
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}


export function createStubDesktopBridge(options: StubDesktopBridgeOptions = {}): DesktopBridge {
  return {
    sessions: {
      createSession: () => httpSessionClient.createSession(),
      startSession: (sessionId, query) => httpSessionClient.startSession(sessionId, { query }),
      stopSession: (sessionId) => httpSessionClient.stopSession(sessionId),
      sendMessage: (sessionId, text) => httpSessionClient.sendMessage(sessionId, { text }),
      getSession: (sessionId) => httpSessionClient.getSession(sessionId),
      getSteps: (sessionId, afterStepId) => httpSessionClient.getSteps(sessionId, afterStepId),
      getVerification: (sessionId) => httpSessionClient.getVerification(sessionId),
    },
    artifacts: {
      resolveUrl: (sessionId, name) => httpArtifactClient.getArtifactHref(sessionId, name),
      readText: (sessionId, name) => httpArtifactClient.readArtifactText(sessionId, name),
      async readBinary(sessionId, name) {
        const artifactHref = httpArtifactClient.getArtifactHref(sessionId, name);
        if (!artifactHref) {
          throw new Error('Failed to resolve artifact');
        }

        const response = await fetch(artifactHref);
        if (!response.ok) {
          throw new Error('Failed to load artifact');
        }

        return encodeBase64(await response.arrayBuffer());
      },
      open: (sessionId, name) => httpArtifactClient.openArtifact(sessionId, name),
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

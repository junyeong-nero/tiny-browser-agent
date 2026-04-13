import type { ArtifactClient } from './artifactClient';
import { getDesktopBridge, type DesktopBridge } from './desktopBridge';


export function createDesktopArtifactClient(bridge: DesktopBridge): ArtifactClient {
  return {
    async openArtifact(sessionId, name) {
      if (!bridge.artifacts) {
        throw new Error('Desktop artifact bridge unavailable');
      }
      await bridge.artifacts.open(sessionId, name);
    },

    async readArtifactBinary(sessionId, name) {
      if (!bridge.artifacts) {
        throw new Error('Desktop artifact bridge unavailable');
      }
      return bridge.artifacts.readBinary(sessionId, name);
    },

    async readArtifactText(sessionId, name) {
      if (!bridge.artifacts) {
        throw new Error('Desktop artifact bridge unavailable');
      }
      return bridge.artifacts.readText(sessionId, name);
    },
  };
}


export function getDesktopArtifactClient(): ArtifactClient | null {
  const bridge = getDesktopBridge();
  if (!bridge?.artifacts) {
    return null;
  }
  return createDesktopArtifactClient(bridge);
}

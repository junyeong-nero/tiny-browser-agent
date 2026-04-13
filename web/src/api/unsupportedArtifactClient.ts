import type { ArtifactClient } from './artifactClient';


function unavailable(): never {
  throw new Error('Desktop bridge unavailable. Start the app from the desktop shell or inject an ArtifactClient explicitly.');
}


export const unsupportedArtifactClient: ArtifactClient = {
  async openArtifact() {
    unavailable();
  },
  async readArtifactBinary() {
    unavailable();
  },
  async readArtifactText() {
    unavailable();
  },
};

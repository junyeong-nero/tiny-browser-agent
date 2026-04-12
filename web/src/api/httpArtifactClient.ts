import type { ArtifactClient } from './artifactClient';


const API_BASE = '/api';


function buildHttpArtifactUrl(sessionId: string, name: string): string {
  return `${API_BASE}/sessions/${sessionId}/artifacts/${name}`;
}


export const httpArtifactClient: ArtifactClient = {
  getArtifactHref(sessionId, name) {
    return buildHttpArtifactUrl(sessionId, name);
  },

  async openArtifact(sessionId, name) {
    const artifactHref = buildHttpArtifactUrl(sessionId, name);
    window.open(artifactHref, '_blank', 'noreferrer');
  },

  async readArtifactText(sessionId, name) {
    const artifactHref = buildHttpArtifactUrl(sessionId, name);
    const response = await fetch(artifactHref);
    if (!response.ok) {
      throw new Error('Failed to load artifact');
    }
    return response.text();
  },
};

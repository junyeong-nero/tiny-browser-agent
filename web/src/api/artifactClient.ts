export interface ArtifactClient {
  getArtifactHref(sessionId: string, name: string): string | null;
  openArtifact(sessionId: string, name: string): Promise<void>;
  readArtifactText(sessionId: string, name: string): Promise<string>;
}

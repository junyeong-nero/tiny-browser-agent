export interface ArtifactClient {
  openArtifact(sessionId: string, name: string): Promise<void>;
  readArtifactBinary(sessionId: string, name: string): Promise<string>;
  readArtifactText(sessionId: string, name: string): Promise<string>;
}

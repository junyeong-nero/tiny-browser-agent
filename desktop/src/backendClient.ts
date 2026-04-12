import { getBackendBaseUrl } from './config';


export class BackendClient {
  constructor(private readonly baseUrl: string = getBackendBaseUrl()) {}

  async healthcheck(): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/health`);
    if (!response.ok) {
      throw new Error(`Backend healthcheck failed with status ${response.status}`);
    }
  }

  async createSession(): Promise<unknown> {
    return this.requestJson('/api/sessions', { method: 'POST' });
  }

  async startSession(sessionId: string, query: string): Promise<void> {
    await this.requestJson(`/api/sessions/${sessionId}/start`, {
      method: 'POST',
      body: JSON.stringify({ query })
    });
  }

  async stopSession(sessionId: string): Promise<void> {
    await this.requestJson(`/api/sessions/${sessionId}/stop`, { method: 'POST' });
  }

  async sendMessage(sessionId: string, text: string): Promise<void> {
    await this.requestJson(`/api/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ text })
    });
  }

  async getSession(sessionId: string): Promise<unknown> {
    return this.requestJson(`/api/sessions/${sessionId}`);
  }

  async getSteps(sessionId: string, afterStepId?: number): Promise<unknown> {
    const searchParams = new URLSearchParams();
    if (afterStepId != null) {
      searchParams.set('after_step_id', String(afterStepId));
    }

    const query = searchParams.toString();
    const route = query
      ? `/api/sessions/${sessionId}/steps?${query}`
      : `/api/sessions/${sessionId}/steps`;

    return this.requestJson(route);
  }

  async getVerification(sessionId: string): Promise<unknown> {
    return this.requestJson(`/api/sessions/${sessionId}/verification`);
  }

  resolveArtifactUrl(sessionId: string, name: string): string {
    return `${this.baseUrl}/api/sessions/${sessionId}/artifacts/${name}`;
  }

  async readArtifactText(sessionId: string, name: string): Promise<string> {
    const response = await fetch(this.resolveArtifactUrl(sessionId, name));
    if (!response.ok) {
      throw new Error(`Artifact request failed with status ${response.status}`);
    }
    return response.text();
  }

  async readArtifactBinary(sessionId: string, name: string): Promise<string> {
    const response = await fetch(this.resolveArtifactUrl(sessionId, name));
    if (!response.ok) {
      throw new Error(`Artifact request failed with status ${response.status}`);
    }

    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = '';
    for (const byte of bytes) {
      binary += String.fromCharCode(byte);
    }
    return Buffer.from(binary, 'binary').toString('base64');
  }

  private async requestJson(route: string, init?: RequestInit): Promise<unknown> {
    const response = await fetch(`${this.baseUrl}${route}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {})
      }
    });

    if (!response.ok) {
      throw new Error(`Backend request failed with status ${response.status}`);
    }

    return response.json();
  }
}

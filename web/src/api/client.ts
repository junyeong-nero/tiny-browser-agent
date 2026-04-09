import type {
  CreateSessionResponse,
  SendMessageRequest,
  SessionSnapshot,
  StartSessionRequest,
  StepRecord,
  VerificationPayload,
} from '../types/api';

const API_BASE = '/api';

export const apiClient = {
  async createSession(): Promise<CreateSessionResponse> {
    const res = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to create session');
    return res.json();
  },

  async startSession(sessionId: string, req: StartSessionRequest): Promise<void> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error('Failed to start session');
  },

  async stopSession(sessionId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/stop`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to stop session');
  },

  async sendMessage(sessionId: string, req: SendMessageRequest): Promise<void> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error('Failed to send message');
  },

  async getSession(sessionId: string): Promise<SessionSnapshot> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
    if (!res.ok) throw new Error('Failed to get session');
    return res.json();
  },

  async getSteps(sessionId: string, afterStepId?: number): Promise<StepRecord[]> {
    const searchParams = new URLSearchParams();
    if (afterStepId != null) {
      searchParams.set('after_step_id', String(afterStepId));
    }
    const queryString = searchParams.toString();
    const url = queryString
      ? `${API_BASE}/sessions/${sessionId}/steps?${queryString}`
      : `${API_BASE}/sessions/${sessionId}/steps`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to get steps');
    return res.json();
  },

  async getVerification(sessionId: string): Promise<VerificationPayload> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/verification`);
    if (!res.ok) throw new Error('Failed to get verification payload');
    return res.json();
  },
};

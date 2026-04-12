import type { SessionClient } from './sessionClient';


const API_BASE = '/api';


export const httpSessionClient: SessionClient = {
  async createSession() {
    const res = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to create session');
    return res.json();
  },

  async startSession(sessionId, req) {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error('Failed to start session');
  },

  async stopSession(sessionId) {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/stop`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to stop session');
  },

  async sendMessage(sessionId, req) {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error('Failed to send message');
  },

  async getSession(sessionId) {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
    if (!res.ok) throw new Error('Failed to get session');
    return res.json();
  },

  async getSteps(sessionId, afterStepId) {
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

  async getVerification(sessionId) {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/verification`);
    if (!res.ok) throw new Error('Failed to get verification payload');
    return res.json();
  },
};

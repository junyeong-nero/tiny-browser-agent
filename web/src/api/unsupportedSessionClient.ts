import type { SessionClient } from './sessionClient';


function unavailable(): never {
  throw new Error('Desktop bridge unavailable. Start the app from the desktop shell or inject a SessionClient explicitly.');
}


export const unsupportedSessionClient: SessionClient = {
  async createSession() {
    unavailable();
  },
  async startSession() {
    unavailable();
  },
  async stopSession() {
    unavailable();
  },
  async sendMessage() {
    unavailable();
  },
  async getSession() {
    unavailable();
  },
  async getSteps() {
    unavailable();
  },
  async getVerification() {
    unavailable();
  },
};

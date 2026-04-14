import type { SessionClient } from './sessionClient';
import type { DesktopBridge } from './desktopBridge';
import { getDesktopBridge } from './desktopBridge';


export function createDesktopSessionClient(bridge: DesktopBridge): SessionClient {
  return {
    createSession() {
      return bridge.sessions.createSession();
    },
    startSession(sessionId, req) {
      return bridge.sessions.startSession(sessionId, req.query);
    },
    stopSession(sessionId) {
      return bridge.sessions.stopSession(sessionId);
    },
    interruptSession(sessionId) {
      return bridge.sessions.interruptSession(sessionId);
    },
    closeSession(sessionId) {
      return bridge.sessions.closeSession(sessionId);
    },
    sendMessage(sessionId, req) {
      return bridge.sessions.sendMessage(sessionId, req.text);
    },
    getSession(sessionId) {
      return bridge.sessions.getSession(sessionId);
    },
    getSteps(sessionId, afterStepId) {
      return bridge.sessions.getSteps(sessionId, afterStepId);
    },
    getVerification(sessionId) {
      return bridge.sessions.getVerification(sessionId);
    },
  };
}


export function getDesktopSessionClient(): SessionClient | null {
  const bridge = getDesktopBridge();
  if (!bridge) {
    return null;
  }
  return createDesktopSessionClient(bridge);
}

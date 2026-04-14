import type {
  CreateSessionResponse,
  SendMessageRequest,
  SessionSnapshot,
  StartSessionRequest,
  StepRecord,
  VerificationPayload,
} from '../types/api';


export interface SessionClient {
  createSession(): Promise<CreateSessionResponse>;
  startSession(sessionId: string, req: StartSessionRequest): Promise<void>;
  stopSession(sessionId: string): Promise<void>;
  interruptSession(sessionId: string): Promise<void>;
  closeSession(sessionId: string): Promise<void>;
  sendMessage(sessionId: string, req: SendMessageRequest): Promise<void>;
  getSession(sessionId: string): Promise<SessionSnapshot>;
  getSteps(sessionId: string, afterStepId?: number): Promise<StepRecord[]>;
  getVerification(sessionId: string): Promise<VerificationPayload>;
}

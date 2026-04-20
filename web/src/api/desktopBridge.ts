import type {
  CreateSessionResponse,
  SessionSnapshot,
  StepRecord,
  VerificationPayload,
} from '../types/api';


export interface DesktopArtifactBridge {
  readText(sessionId: string, name: string): Promise<string>;
  readBinary(sessionId: string, name: string): Promise<string>;
  open(sessionId: string, name: string): Promise<void>;
}


export interface BrowserSurfaceBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}


export interface BrowserSurfaceFrame {
  url: string;
  mimeType: 'image/jpeg';
  base64: string;
}


export interface DesktopBrowserSurfaceBridge {
  focus(): Promise<void> | void;
  setBounds(bounds: BrowserSurfaceBounds): Promise<void> | void;
  onFrame?(listener: (frame: BrowserSurfaceFrame) => void): () => void;
}


export interface DesktopSessionBridge {
  createSession(): Promise<CreateSessionResponse>;
  startSession(sessionId: string, query: string, modelName?: string): Promise<void>;
  stopSession(sessionId: string): Promise<void>;
  interruptSession(sessionId: string): Promise<void>;
  closeSession(sessionId: string): Promise<void>;
  sendMessage(sessionId: string, text: string): Promise<void>;
  getSession(sessionId: string): Promise<SessionSnapshot>;
  getSteps(sessionId: string, afterStepId?: number): Promise<StepRecord[]>;
  getVerification(sessionId: string): Promise<VerificationPayload>;
}


export interface DesktopBridge {
  sessions: DesktopSessionBridge;
  artifacts?: DesktopArtifactBridge;
  browserSurface?: DesktopBrowserSurfaceBridge;
}


export type DesktopBridgeHost = typeof globalThis & {
  __COMPUTER_USE_DESKTOP_BRIDGE__?: DesktopBridge;
  __COMPUTER_USE_DESKTOP_HOST__?: boolean;
  __COMPUTER_USE_ENABLE_DESKTOP_STUB__?: boolean;
};


export function getDesktopBridge(
  host: DesktopBridgeHost = globalThis as DesktopBridgeHost,
): DesktopBridge | null {
  return host.__COMPUTER_USE_DESKTOP_BRIDGE__ ?? null;
}


export function installDesktopBridge(
  bridge: DesktopBridge,
  host: DesktopBridgeHost = globalThis as DesktopBridgeHost,
): DesktopBridge {
  host.__COMPUTER_USE_DESKTOP_BRIDGE__ = bridge;
  return bridge;
}


export function markDesktopHost(
  host: DesktopBridgeHost = globalThis as DesktopBridgeHost,
): void {
  host.__COMPUTER_USE_DESKTOP_HOST__ = true;
}


export function clearDesktopBridge(
  host: DesktopBridgeHost = globalThis as DesktopBridgeHost,
): void {
  delete host.__COMPUTER_USE_DESKTOP_BRIDGE__;
}


export function clearDesktopHost(
  host: DesktopBridgeHost = globalThis as DesktopBridgeHost,
): void {
  delete host.__COMPUTER_USE_DESKTOP_HOST__;
}


export function hasDesktopBridge(host?: DesktopBridgeHost): boolean {
  return getDesktopBridge(host) !== null;
}


export function isDesktopHost(
  host: DesktopBridgeHost = globalThis as DesktopBridgeHost,
): boolean {
  return host.__COMPUTER_USE_DESKTOP_HOST__ === true;
}


declare global {
  interface Window {
    __COMPUTER_USE_DESKTOP_BRIDGE__?: DesktopBridge;
    __COMPUTER_USE_DESKTOP_HOST__?: boolean;
    __COMPUTER_USE_ENABLE_DESKTOP_STUB__?: boolean;
  }
}

export const BRIDGE_CHANNELS = {
  createSession: 'computer-use:sessions:create',
  startSession: 'computer-use:sessions:start',
  stopSession: 'computer-use:sessions:stop',
  sendMessage: 'computer-use:sessions:send-message',
  getSession: 'computer-use:sessions:get',
  getSteps: 'computer-use:sessions:get-steps',
  getVerification: 'computer-use:sessions:get-verification',
  getArtifactText: 'computer-use:artifacts:get-text',
  getArtifactBinary: 'computer-use:artifacts:get-binary',
  openArtifact: 'computer-use:artifacts:open',
  resolveArtifactUrl: 'computer-use:artifacts:resolve-url',
  focusBrowserSurface: 'computer-use:browser-surface:focus',
  setBrowserSurfaceBounds: 'computer-use:browser-surface:set-bounds'
} as const;

export interface BrowserSurfaceBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

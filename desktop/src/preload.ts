import { contextBridge, ipcRenderer } from 'electron';

import { BRIDGE_CHANNELS, type BrowserSurfaceBounds } from './bridge/channels';


contextBridge.exposeInMainWorld('__COMPUTER_USE_DESKTOP_HOST__', true);

contextBridge.exposeInMainWorld('__COMPUTER_USE_DESKTOP_BRIDGE__', {
  sessions: {
    createSession: () => ipcRenderer.invoke(BRIDGE_CHANNELS.createSession),
    startSession: (sessionId: string, query: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.startSession, { sessionId, query }),
    stopSession: (sessionId: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.stopSession, { sessionId }),
    interruptSession: (sessionId: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.interruptSession, { sessionId }),
    closeSession: (sessionId: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.closeSession, { sessionId }),
    sendMessage: (sessionId: string, text: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.sendMessage, { sessionId, text }),
    getSession: (sessionId: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.getSession, { sessionId }),
    getSteps: (sessionId: string, afterStepId?: number) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.getSteps, { sessionId, afterStepId }),
    getVerification: (sessionId: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.getVerification, { sessionId })
  },
  artifacts: {
    readText: (sessionId: string, name: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.getArtifactText, { sessionId, name }),
    readBinary: (sessionId: string, name: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.getArtifactBinary, { sessionId, name }),
    open: (sessionId: string, name: string) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.openArtifact, { sessionId, name })
  },
  browserSurface: {
    focus: () => ipcRenderer.invoke(BRIDGE_CHANNELS.focusBrowserSurface),
    setBounds: (bounds: BrowserSurfaceBounds) =>
      ipcRenderer.invoke(BRIDGE_CHANNELS.setBrowserSurfaceBounds, { bounds })
  }
});

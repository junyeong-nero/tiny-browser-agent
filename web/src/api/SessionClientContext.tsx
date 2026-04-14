import { createContext, useContext, type ReactNode } from 'react';

import { createBridgeAwareClient, resolveBridgeBackedClient } from './bridgeClientResolver';
import { isDesktopHost } from './desktopBridge';
import { getDesktopSessionClient } from './desktopSessionClient';
import { httpSessionClient } from './httpSessionClient';
import type { SessionClient } from './sessionClient';
import { unsupportedSessionClient } from './unsupportedSessionClient';


const SessionClientContext = createContext<SessionClient>(unsupportedSessionClient);

function getDefaultSessionClient(): SessionClient {
  return resolveBridgeBackedClient({
    getDesktopClient: getDesktopSessionClient,
    httpClient: httpSessionClient,
    unsupportedClient: unsupportedSessionClient,
    isDesktopHost: isDesktopHost(),
  });
}

const bridgeAwareSessionClient = createBridgeAwareClient<SessionClient>(getDefaultSessionClient);


export function resolveSessionClient(client?: SessionClient): SessionClient {
  return resolveBridgeBackedClient({
    explicitClient: client,
    getDesktopClient: getDesktopSessionClient,
    httpClient: httpSessionClient,
    unsupportedClient: unsupportedSessionClient,
    isDesktopHost: isDesktopHost(),
  });
}


interface SessionClientProviderProps {
  children: ReactNode;
  client?: SessionClient;
}


export function SessionClientProvider({ children, client }: SessionClientProviderProps) {
  const resolvedClient = client ?? bridgeAwareSessionClient;

  return (
    <SessionClientContext.Provider value={resolvedClient}>
      {children}
    </SessionClientContext.Provider>
  );
}


export function useSessionClient(): SessionClient {
  return useContext(SessionClientContext);
}

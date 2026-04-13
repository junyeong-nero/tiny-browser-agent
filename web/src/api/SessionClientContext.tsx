import { createContext, useContext, useMemo, type ReactNode } from 'react';

import { getDesktopSessionClient } from './desktopSessionClient';
import type { SessionClient } from './sessionClient';
import { unsupportedSessionClient } from './unsupportedSessionClient';


const SessionClientContext = createContext<SessionClient>(unsupportedSessionClient);


export function resolveSessionClient(client?: SessionClient): SessionClient {
  if (client) {
    return client;
  }

  const desktopClient = getDesktopSessionClient();
  if (desktopClient) {
    return desktopClient;
  }

  return unsupportedSessionClient;
}


interface SessionClientProviderProps {
  children: ReactNode;
  client?: SessionClient;
}


export function SessionClientProvider({ children, client }: SessionClientProviderProps) {
  const resolvedClient = useMemo(() => resolveSessionClient(client), [client]);

  return (
    <SessionClientContext.Provider value={resolvedClient}>
      {children}
    </SessionClientContext.Provider>
  );
}


export function useSessionClient(): SessionClient {
  return useContext(SessionClientContext);
}

import { createContext, useContext, useMemo, type ReactNode } from 'react';

import type { ArtifactClient } from './artifactClient';
import { getDesktopArtifactClient } from './desktopArtifactClient';
import { httpArtifactClient } from './httpArtifactClient';


const ArtifactClientContext = createContext<ArtifactClient>(httpArtifactClient);


interface ArtifactClientProviderProps {
  children: ReactNode;
  client?: ArtifactClient;
}


export function resolveArtifactClient(client?: ArtifactClient): ArtifactClient {
  if (client) {
    return client;
  }

  const desktopClient = getDesktopArtifactClient();
  if (desktopClient) {
    return desktopClient;
  }

  return httpArtifactClient;
}


export function ArtifactClientProvider({ children, client }: ArtifactClientProviderProps) {
  const resolvedClient = useMemo(() => resolveArtifactClient(client), [client]);

  return (
    <ArtifactClientContext.Provider value={resolvedClient}>
      {children}
    </ArtifactClientContext.Provider>
  );
}


export function useArtifactClient(): ArtifactClient {
  return useContext(ArtifactClientContext);
}

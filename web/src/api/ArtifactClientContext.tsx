import { createContext, useContext, type ReactNode } from 'react';

import type { ArtifactClient } from './artifactClient';
import { createBridgeAwareClient, resolveBridgeBackedClient } from './bridgeClientResolver';
import { isDesktopHost } from './desktopBridge';
import { getDesktopArtifactClient } from './desktopArtifactClient';
import { httpArtifactClient } from './httpArtifactClient';
import { unsupportedArtifactClient } from './unsupportedArtifactClient';


const ArtifactClientContext = createContext<ArtifactClient>(unsupportedArtifactClient);

function getDefaultArtifactClient(): ArtifactClient {
  return resolveBridgeBackedClient({
    getDesktopClient: getDesktopArtifactClient,
    httpClient: httpArtifactClient,
    unsupportedClient: unsupportedArtifactClient,
    isDesktopHost: isDesktopHost(),
  });
}

const bridgeAwareArtifactClient = createBridgeAwareClient<ArtifactClient>(getDefaultArtifactClient);


interface ArtifactClientProviderProps {
  children: ReactNode;
  client?: ArtifactClient;
}


export function resolveArtifactClient(client?: ArtifactClient): ArtifactClient {
  return resolveBridgeBackedClient({
    explicitClient: client,
    getDesktopClient: getDesktopArtifactClient,
    httpClient: httpArtifactClient,
    unsupportedClient: unsupportedArtifactClient,
    isDesktopHost: isDesktopHost(),
  });
}


export function ArtifactClientProvider({ children, client }: ArtifactClientProviderProps) {
  const resolvedClient = client ?? bridgeAwareArtifactClient;

  return (
    <ArtifactClientContext.Provider value={resolvedClient}>
      {children}
    </ArtifactClientContext.Provider>
  );
}


export function useArtifactClient(): ArtifactClient {
  return useContext(ArtifactClientContext);
}

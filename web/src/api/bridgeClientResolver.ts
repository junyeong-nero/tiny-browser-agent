export interface BridgeClientResolverOptions<T> {
  explicitClient?: T;
  getDesktopClient: () => T | null;
  httpClient: T;
  unsupportedClient: T;
  isDesktopHost: boolean;
}

export function resolveBridgeBackedClient<T>({
  explicitClient,
  getDesktopClient,
  httpClient,
  unsupportedClient,
  isDesktopHost,
}: BridgeClientResolverOptions<T>): T {
  if (explicitClient) {
    return explicitClient;
  }

  const desktopClient = getDesktopClient();
  if (desktopClient) {
    return desktopClient;
  }

  if (isDesktopHost) {
    return unsupportedClient;
  }

  return httpClient;
}

export function createBridgeAwareClient<T extends object>(resolveClient: () => T): T {
  return new Proxy({} as T, {
    get(_target, property, receiver) {
      const client = resolveClient();
      const value = Reflect.get(client as object, property, receiver);
      return typeof value === 'function' ? value.bind(client) : value;
    },
  });
}

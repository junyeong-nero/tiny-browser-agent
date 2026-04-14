import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';

import type { BrowserSurfaceBounds } from './bridge/channels';
import type { BrowserSurfaceState, BrowserSurfaceManager } from './browserSurfaceManager';


interface JsonObject {
  [key: string]: unknown;
}

type BrowserCommandPayload = JsonObject | BrowserSurfaceState;

interface BrowserCommandRoute {
  method: 'GET' | 'POST';
  path: string;
  handle: (payload: JsonObject) => Promise<BrowserCommandPayload>;
}


export function createBrowserCommandRoutes(
  browserSurfaceManager: BrowserSurfaceManager,
): BrowserCommandRoute[] {
  const captureState = () => browserSurfaceManager.captureState();

  return [
    {
      method: 'GET',
      path: '/health',
      async handle() {
        return { status: 'ok' };
      },
    },
    {
      method: 'GET',
      path: '/computer/screen-size',
      async handle() {
        return browserSurfaceManager.getScreenSize();
      },
    },
    {
      method: 'POST',
      path: '/computer/state',
      async handle() {
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/navigate',
      async handle(payload) {
        await browserSurfaceManager.navigate(readString(payload, 'url'));
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/go-back',
      async handle() {
        await browserSurfaceManager.goBack();
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/go-forward',
      async handle() {
        await browserSurfaceManager.goForward();
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/click-at',
      async handle(payload) {
        await browserSurfaceManager.clickAt(readNumber(payload, 'x'), readNumber(payload, 'y'));
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/hover-at',
      async handle(payload) {
        await browserSurfaceManager.hoverAt(readNumber(payload, 'x'), readNumber(payload, 'y'));
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/type-text-at',
      async handle(payload) {
        await browserSurfaceManager.typeTextAt(
          readNumber(payload, 'x'),
          readNumber(payload, 'y'),
          readString(payload, 'text'),
          readBoolean(payload, 'pressEnter', false),
          readBoolean(payload, 'clearBeforeTyping', true),
        );
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/scroll-document',
      async handle(payload) {
        await browserSurfaceManager.scrollDocument(readDirection(payload, 'direction'));
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/scroll-at',
      async handle(payload) {
        await browserSurfaceManager.scrollAt(
          readNumber(payload, 'x'),
          readNumber(payload, 'y'),
          readDirection(payload, 'direction'),
          readNumber(payload, 'magnitude'),
        );
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/key-combination',
      async handle(payload) {
        await browserSurfaceManager.keyCombination(readStringArray(payload, 'keys'));
        return captureState();
      },
    },
    {
      method: 'POST',
      path: '/computer/drag-and-drop',
      async handle(payload) {
        await browserSurfaceManager.dragAndDrop(
          readNumber(payload, 'x'),
          readNumber(payload, 'y'),
          readNumber(payload, 'destinationX'),
          readNumber(payload, 'destinationY'),
        );
        return captureState();
      },
    },
  ];
}


export async function handleBrowserCommandRequest(
  browserSurfaceManager: BrowserSurfaceManager,
  method: string,
  path: string,
  payload: JsonObject = {},
): Promise<{ status: number; payload: BrowserCommandPayload }> {
  const route = createBrowserCommandRoutes(browserSurfaceManager).find(
    (candidate) => candidate.method === method && candidate.path === path,
  );
  if (!route) {
    return { status: 404, payload: { error: 'Not found' } };
  }

  return {
    status: 200,
    payload: await route.handle(payload),
  };
}


export class BrowserCommandServer {
  private server: ReturnType<typeof createServer> | null = null;
  private baseUrl: string | null = null;

  constructor(private readonly browserSurfaceManager: BrowserSurfaceManager) {}

  async start(): Promise<string> {
    if (this.server && this.baseUrl) {
      return this.baseUrl;
    }

    this.server = createServer((request, response) => {
      void this.handleRequest(request, response);
    });

    await new Promise<void>((resolve, reject) => {
      this.server?.once('error', reject);
      this.server?.listen(0, '127.0.0.1', () => {
        resolve();
      });
    });

    const address = this.server.address();
    if (!address || typeof address === 'string') {
      throw new Error('Failed to determine browser command server address');
    }

    this.baseUrl = `http://127.0.0.1:${(address as AddressInfo).port}`;
    return this.baseUrl;
  }

  async stop(): Promise<void> {
    if (!this.server) {
      return;
    }

    await new Promise<void>((resolve, reject) => {
      this.server?.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      });
    });

    this.server = null;
    this.baseUrl = null;
  }

  private async handleRequest(
    request: IncomingMessage,
    response: ServerResponse,
  ): Promise<void> {
    try {
      const method = request.method ?? 'GET';
      const url = new URL(request.url ?? '/', 'http://127.0.0.1');
      const payload = method === 'POST' ? await this.readJsonBody(request) : {};
      const result = await handleBrowserCommandRequest(
        this.browserSurfaceManager,
        method,
        url.pathname,
        payload,
      );
      this.respondJson(response, result.status, result.payload);
    } catch (error) {
      this.respondJson(response, 500, {
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }

  private respondJson(response: ServerResponse, status: number, payload: BrowserCommandPayload): void {
    response.statusCode = status;
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify(payload));
  }

  private async readJsonBody(request: IncomingMessage): Promise<JsonObject> {
    const chunks: Buffer[] = [];
    for await (const chunk of request) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }

    if (chunks.length === 0) {
      return {};
    }

    return JSON.parse(Buffer.concat(chunks).toString('utf-8')) as JsonObject;
  }
}


function readString(payload: JsonObject, key: string): string {
  const value = payload[key];
  if (typeof value !== 'string') {
    throw new Error(`Expected string field '${key}'`);
  }
  return value;
}


function readNumber(payload: JsonObject, key: string): number {
  const value = payload[key];
  if (typeof value !== 'number') {
    throw new Error(`Expected numeric field '${key}'`);
  }
  return value;
}


function readBoolean(payload: JsonObject, key: string, fallback: boolean): boolean {
  const value = payload[key];
  if (value == null) {
    return fallback;
  }
  if (typeof value !== 'boolean') {
    throw new Error(`Expected boolean field '${key}'`);
  }
  return value;
}


function readStringArray(payload: JsonObject, key: string): string[] {
  const value = payload[key];
  if (!Array.isArray(value) || value.some((entry) => typeof entry !== 'string')) {
    throw new Error(`Expected string[] field '${key}'`);
  }
  return value;
}


function readDirection(
  payload: JsonObject,
  key: string,
): BrowserSurfaceBounds extends never ? never : 'up' | 'down' | 'left' | 'right' {
  const value = payload[key];
  if (value !== 'up' && value !== 'down' && value !== 'left' && value !== 'right') {
    throw new Error(`Expected scroll direction field '${key}'`);
  }
  return value;
}

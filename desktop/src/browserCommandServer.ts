import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';

import type { BrowserSurfaceBounds } from './bridge/channels';
import type { BrowserSurfaceState, BrowserSurfaceManager } from './browserSurfaceManager';


interface JsonObject {
  [key: string]: unknown;
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

      if (method === 'GET' && url.pathname === '/health') {
        this.respondJson(response, 200, { status: 'ok' });
        return;
      }

      if (method === 'GET' && url.pathname === '/computer/screen-size') {
        this.respondJson(response, 200, this.browserSurfaceManager.getScreenSize());
        return;
      }

      const payload = method === 'POST' ? await this.readJsonBody(request) : {};

      if (method === 'POST' && url.pathname === '/computer/state') {
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/navigate') {
        await this.browserSurfaceManager.navigate(readString(payload, 'url'));
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/go-back') {
        await this.browserSurfaceManager.goBack();
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/go-forward') {
        await this.browserSurfaceManager.goForward();
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/click-at') {
        await this.browserSurfaceManager.clickAt(readNumber(payload, 'x'), readNumber(payload, 'y'));
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/hover-at') {
        await this.browserSurfaceManager.hoverAt(readNumber(payload, 'x'), readNumber(payload, 'y'));
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/type-text-at') {
        await this.browserSurfaceManager.typeTextAt(
          readNumber(payload, 'x'),
          readNumber(payload, 'y'),
          readString(payload, 'text'),
          readBoolean(payload, 'pressEnter', false),
          readBoolean(payload, 'clearBeforeTyping', true),
        );
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/scroll-document') {
        await this.browserSurfaceManager.scrollDocument(
          readDirection(payload, 'direction'),
        );
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/scroll-at') {
        await this.browserSurfaceManager.scrollAt(
          readNumber(payload, 'x'),
          readNumber(payload, 'y'),
          readDirection(payload, 'direction'),
          readNumber(payload, 'magnitude'),
        );
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/key-combination') {
        await this.browserSurfaceManager.keyCombination(readStringArray(payload, 'keys'));
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      if (method === 'POST' && url.pathname === '/computer/drag-and-drop') {
        await this.browserSurfaceManager.dragAndDrop(
          readNumber(payload, 'x'),
          readNumber(payload, 'y'),
          readNumber(payload, 'destinationX'),
          readNumber(payload, 'destinationY'),
        );
        this.respondJson(response, 200, await this.browserSurfaceManager.captureState());
        return;
      }

      this.respondJson(response, 404, { error: 'Not found' });
    } catch (error) {
      this.respondJson(response, 500, {
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }

  private respondJson(response: ServerResponse, status: number, payload: JsonObject | BrowserSurfaceState): void {
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

import { createInterface, type Interface } from 'node:readline';
import type { ChildProcessWithoutNullStreams } from 'node:child_process';


interface BridgeRequest {
  id: string;
  method: string;
  params: Record<string, unknown>;
}


interface BridgeResponse {
  id: string | null;
  ok: boolean;
  result?: unknown;
  error?: {
    code?: string;
    message?: string;
  };
}


interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (reason?: unknown) => void;
}


export class PythonBridgeClient {
  private readonly pendingRequests = new Map<string, PendingRequest>();
  private readonly reader: Interface;
  private nextRequestId = 0;

  constructor(private readonly pythonProcess: ChildProcessWithoutNullStreams) {
    this.reader = createInterface({ input: pythonProcess.stdout });
    this.reader.on('line', (line) => {
      this.handleLine(line);
    });
    pythonProcess.on('exit', () => {
      this.rejectAllPending(new Error('Python bridge exited.'));
    });
    pythonProcess.on('error', (error) => {
      this.rejectAllPending(error);
    });
  }

  async healthcheck(): Promise<void> {
    await this.call('healthcheck');
  }

  createSession(): Promise<unknown> {
    return this.call('createSession');
  }

  startSession(sessionId: string, query: string): Promise<unknown> {
    return this.call('startSession', { query, sessionId });
  }

  stopSession(sessionId: string): Promise<unknown> {
    return this.call('stopSession', { sessionId });
  }

  interruptSession(sessionId: string): Promise<unknown> {
    return this.call('interruptSession', { sessionId });
  }

  closeSession(sessionId: string): Promise<unknown> {
    return this.call('closeSession', { sessionId });
  }

  sendMessage(sessionId: string, text: string): Promise<unknown> {
    return this.call('sendMessage', { sessionId, text });
  }

  getSession(sessionId: string): Promise<unknown> {
    return this.call('getSession', { sessionId });
  }

  getSteps(sessionId: string, afterStepId?: number): Promise<unknown> {
    return this.call('getSteps', { afterStepId, sessionId });
  }

  getVerification(sessionId: string): Promise<unknown> {
    return this.call('getVerification', { sessionId });
  }

  readArtifactText(sessionId: string, name: string): Promise<string> {
    return this.call('readArtifactText', { name, sessionId }) as Promise<string>;
  }

  readArtifactBinary(sessionId: string, name: string): Promise<string> {
    return this.call('readArtifactBinary', { name, sessionId }) as Promise<string>;
  }

  resolveArtifactPath(sessionId: string, name: string): Promise<string> {
    return this.call('resolveArtifactPath', { name, sessionId }) as Promise<string>;
  }

  dispose(): void {
    this.reader.close();
    this.rejectAllPending(new Error('Python bridge disposed.'));
  }

  private call(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    const id = `req_${this.nextRequestId}`;
    this.nextRequestId += 1;

    const request: BridgeRequest = {
      id,
      method,
      params,
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { reject, resolve });
      this.pythonProcess.stdin.write(JSON.stringify(request) + '\n');
    });
  }

  private handleLine(line: string): void {
    let response: BridgeResponse;
    try {
      response = JSON.parse(line) as BridgeResponse;
    } catch (_error) {
      return;
    }

    if (!response.id) {
      return;
    }

    const pendingRequest = this.pendingRequests.get(response.id);
    if (!pendingRequest) {
      return;
    }
    this.pendingRequests.delete(response.id);

    if (!response.ok) {
      pendingRequest.reject(new Error(response.error?.message ?? 'Python bridge request failed.'));
      return;
    }

    pendingRequest.resolve(response.result);
  }

  private rejectAllPending(error: Error): void {
    for (const pendingRequest of this.pendingRequests.values()) {
      pendingRequest.reject(error);
    }
    this.pendingRequests.clear();
  }
}

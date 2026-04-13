import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';

import { REPO_ROOT } from './config';
import { PythonBridgeClient } from './pythonBridgeClient';


export interface PythonRuntime {
  client: PythonBridgeClient;
  process: ChildProcessWithoutNullStreams;
  stop: () => void;
}


export async function startPythonRuntime(electronCommandUrl: string): Promise<PythonRuntime> {
  const command = process.env.COMPUTER_USE_PYTHON_COMMAND ?? 'uv';
  const args = [
    'run',
    'python',
    'main.py',
    '--desktop_bridge',
    '--headless',
    'True',
  ];

  const pythonProcess = spawn(command, args, {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      COMPUTER_USE_ELECTRON_COMMAND_URL: electronCommandUrl,
    },
    stdio: 'pipe'
  });

  pythonProcess.stderr.on('data', (chunk) => {
    process.stderr.write(`[python] ${chunk}`);
  });

  const client = new PythonBridgeClient(pythonProcess);
  await client.healthcheck();

  return {
    client,
    process: pythonProcess,
    stop: () => {
      client.dispose();
      if (!pythonProcess.killed) {
        pythonProcess.kill();
      }
    }
  };
}

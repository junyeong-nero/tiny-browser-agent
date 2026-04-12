import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';

import { DEFAULT_BACKEND_HOST, DEFAULT_BACKEND_PORT, REPO_ROOT } from './config';


export interface PythonRuntime {
  process: ChildProcessWithoutNullStreams;
  stop: () => void;
}


export async function startPythonRuntime(electronCommandUrl: string): Promise<PythonRuntime> {
  const command = process.env.COMPUTER_USE_PYTHON_COMMAND ?? 'uv';
  const args = [
    'run',
    'python',
    'main.py',
    '--ui',
    '--headless',
    'True',
    '--ui_host',
    DEFAULT_BACKEND_HOST,
    '--ui_port',
    String(DEFAULT_BACKEND_PORT)
  ];

  const pythonProcess = spawn(command, args, {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      COMPUTER_USE_ELECTRON_COMMAND_URL: electronCommandUrl,
    },
    stdio: 'pipe'
  });

  pythonProcess.stdout.on('data', (chunk) => {
    process.stdout.write(`[python] ${chunk}`);
  });
  pythonProcess.stderr.on('data', (chunk) => {
    process.stderr.write(`[python] ${chunk}`);
  });

  return {
    process: pythonProcess,
    stop: () => {
      if (!pythonProcess.killed) {
        pythonProcess.kill();
      }
    }
  };
}

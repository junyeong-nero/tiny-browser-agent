import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';


test('desktop start builds the renderer and desktop bundles before launching Electron', () => {
  const packageJsonPath = path.resolve(__dirname, '..', 'package.json');
  const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf8')) as {
    scripts?: Record<string, string>;
  };

  assert.equal(
    packageJson.scripts?.prestart,
    'npm run renderer:build && npm run build',
  );
  assert.equal(packageJson.scripts?.start, 'electron dist/main.js');
});

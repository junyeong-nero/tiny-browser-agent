import type { BrowserSurfaceState, ManagedBrowserSurfaceView } from './browserSurfaceManager';

const EMPTY_SCREENSHOT_RETRY_DELAY_MS = 100;
const MAX_EMPTY_SCREENSHOT_ATTEMPTS = 3;

export async function captureBrowserSurfaceState(
  browserSurfaceView: ManagedBrowserSurfaceView,
  screenSize: { width: number; height: number },
): Promise<BrowserSurfaceState> {
  const screenshot = await captureScreenshotWithRetry(browserSurfaceView);
  const html = await safeReadHtml(browserSurfaceView);
  const a11ySnapshot = await captureAccessibilitySnapshot(browserSurfaceView);
  const url = browserSurfaceView.webContents.getURL();

  return {
    screenshotBase64: screenshot.toString('base64'),
    url,
    html,
    a11yText: a11ySnapshot.text,
    a11ySource: a11ySnapshot.source,
    a11yCaptureStatus: a11ySnapshot.status,
    a11yCaptureError: a11ySnapshot.error,
    width: screenSize.width,
    height: screenSize.height,
  };
}

async function captureScreenshotWithRetry(
  browserSurfaceView: ManagedBrowserSurfaceView,
): Promise<Buffer> {
  for (let attempt = 1; attempt <= MAX_EMPTY_SCREENSHOT_ATTEMPTS; attempt += 1) {
    const screenshot = await browserSurfaceView.webContents.captureScreenshot();
    if (screenshot.length > 0) {
      return screenshot;
    }

    if (attempt < MAX_EMPTY_SCREENSHOT_ATTEMPTS) {
      await wait(EMPTY_SCREENSHOT_RETRY_DELAY_MS);
    }
  }

  throw new Error(
    'Browser surface screenshot capture returned an empty PNG buffer.',
  );
}

async function safeReadHtml(browserSurfaceView: ManagedBrowserSurfaceView): Promise<string | null> {
  try {
    return (await browserSurfaceView.webContents.runScript(
      'document.documentElement ? document.documentElement.outerHTML : null',
    )) as string | null;
  } catch (_error) {
    return null;
  }
}

async function captureAccessibilitySnapshot(
  browserSurfaceView: ManagedBrowserSurfaceView,
): Promise<{
  text: string | null;
  source: string;
  status: 'captured' | 'error';
  error: string | null;
}> {
  const source = 'dom_accessibility_outline';

  try {
    const text = (await browserSurfaceView.webContents.runScript(`
      (() => {
        const lines = [];

        function visit(node, depth) {
          if (!(node instanceof HTMLElement)) {
            return;
          }

          const role = node.getAttribute('role') || node.tagName.toLowerCase();
          const label =
            node.getAttribute('aria-label') ||
            (node instanceof HTMLInputElement ? node.value || node.placeholder || '' : '') ||
            (node.innerText || '').trim().split('\\n')[0];

          if (role || label) {
            const prefix = '  '.repeat(depth);
            lines.push(prefix + '- ' + role + (label ? ': ' + label : ''));
          }

          for (const child of Array.from(node.children).slice(0, 40)) {
            visit(child, depth + 1);
          }
        }

        visit(document.body, 0);
        return lines.join('\\n');
      })();
    `)) as string | null;

    return {
      text: text || null,
      source,
      status: 'captured',
      error: null,
    };
  } catch (error) {
    return {
      text: null,
      source,
      status: 'error',
      error: error instanceof Error ? error.message : 'Unknown accessibility capture error',
    };
  }
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

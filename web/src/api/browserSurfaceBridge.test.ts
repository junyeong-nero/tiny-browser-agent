import { describe, expect, it, vi } from 'vitest';

import {
  focusBrowserSurface,
  measureBrowserSurfaceBounds,
  syncBrowserSurfaceBounds,
} from './browserSurfaceBridge';
import type { DesktopBrowserSurfaceBridge } from './desktopBridge';


describe('browserSurfaceBridge', () => {
  it('measures bounds from the host element rect', () => {
    const element = {
      getBoundingClientRect: () => ({
        left: 10,
        top: 20,
        width: 300,
        height: 200,
      }),
    } as Element;

    expect(measureBrowserSurfaceBounds(element)).toEqual({
      x: 10,
      y: 20,
      width: 300,
      height: 200,
    });
  });

  it('syncs measured bounds to the desktop browser surface bridge', () => {
    const bridge: DesktopBrowserSurfaceBridge = {
      focus: vi.fn(),
      setBounds: vi.fn(),
    };
    const element = {
      getBoundingClientRect: () => ({
        left: 15,
        top: 25,
        width: 320,
        height: 180,
      }),
    } as Element;

    syncBrowserSurfaceBounds(element, bridge);

    expect(bridge.setBounds).toHaveBeenCalledWith({
      x: 15,
      y: 25,
      width: 320,
      height: 180,
    });
  });

  it('hides the browser surface when visibility is disabled', () => {
    const bridge: DesktopBrowserSurfaceBridge = {
      focus: vi.fn(),
      setBounds: vi.fn(),
    };
    const element = {
      getBoundingClientRect: () => ({
        left: 15,
        top: 25,
        width: 320,
        height: 180,
      }),
    } as Element;

    syncBrowserSurfaceBounds(element, bridge, false);

    expect(bridge.setBounds).toHaveBeenCalledWith({ x: 0, y: 0, width: 0, height: 0 });
  });

  it('delegates focus to the desktop browser surface when available', async () => {
    const bridge: DesktopBrowserSurfaceBridge = {
      focus: vi.fn().mockResolvedValue(undefined),
      setBounds: vi.fn(),
    };
    const element = {
      focus: vi.fn(),
    } as unknown as HTMLElement;

    await focusBrowserSurface(element, bridge);

    expect(bridge.focus).toHaveBeenCalledTimes(1);
    expect(element.focus).not.toHaveBeenCalled();
  });

  it('falls back to DOM focus when no bridge is available', async () => {
    const element = {
      focus: vi.fn(),
    } as unknown as HTMLElement;

    await focusBrowserSurface(element, null);

    expect(element.focus).toHaveBeenCalledTimes(1);
  });
});

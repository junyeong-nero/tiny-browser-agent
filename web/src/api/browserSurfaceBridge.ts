import { useCallback, useEffect, type RefObject } from 'react';

import {
  getDesktopBridge,
  type BrowserSurfaceBounds,
  type DesktopBrowserSurfaceBridge,
} from './desktopBridge';


interface BrowserSurfaceHostOptions {
  isVisible?: boolean;
}


export function getBrowserSurfaceBridge(): DesktopBrowserSurfaceBridge | null {
  return getDesktopBridge()?.browserSurface ?? null;
}


export function measureBrowserSurfaceBounds(element: Element): BrowserSurfaceBounds {
  const rect = element.getBoundingClientRect();
  return {
    x: rect.left,
    y: rect.top,
    width: rect.width,
    height: rect.height,
  };
}


export function syncBrowserSurfaceBounds(
  element: Element | null | undefined,
  bridge: DesktopBrowserSurfaceBridge | null = getBrowserSurfaceBridge(),
  isVisible = true,
): void {
  if (!element || !bridge) {
    return;
  }

  if (!isVisible) {
    bridge.setBounds({ x: 0, y: 0, width: 0, height: 0 });
    return;
  }

  bridge.setBounds(measureBrowserSurfaceBounds(element));
}


export async function focusBrowserSurface(
  element: HTMLElement | null | undefined,
  bridge: DesktopBrowserSurfaceBridge | null = getBrowserSurfaceBridge(),
): Promise<void> {
  if (bridge) {
    await bridge.focus();
    return;
  }

  element?.focus();
}


export function useBrowserSurfaceHost<T extends HTMLElement>(
  hostRef: RefObject<T | null>,
  options: BrowserSurfaceHostOptions = {},
) {
  const browserSurfaceBridge = getBrowserSurfaceBridge();
  const isVisible = options.isVisible ?? true;

  const syncBounds = useCallback(() => {
    syncBrowserSurfaceBounds(hostRef.current, browserSurfaceBridge, isVisible);
  }, [browserSurfaceBridge, hostRef, isVisible]);

  const focusSurface = useCallback(async () => {
    await focusBrowserSurface(hostRef.current, browserSurfaceBridge);
  }, [browserSurfaceBridge, hostRef]);

  useEffect(() => {
    const hostElement = hostRef.current;
    if (!hostElement || !browserSurfaceBridge) {
      return undefined;
    }

    syncBounds();

    const handleViewportChange = () => {
      syncBounds();
    };

    const resizeObserver =
      typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(() => {
            syncBounds();
          });

    resizeObserver?.observe(hostElement);
    window.addEventListener('resize', handleViewportChange);
    window.addEventListener('scroll', handleViewportChange, true);

    return () => {
      resizeObserver?.disconnect();
      window.removeEventListener('resize', handleViewportChange);
      window.removeEventListener('scroll', handleViewportChange, true);
    };
  }, [browserSurfaceBridge, hostRef, syncBounds]);

  return {
    hasBrowserSurfaceBridge: browserSurfaceBridge !== null,
    focusBrowserSurface: focusSurface,
    syncBrowserSurfaceBounds: syncBounds,
  };
}

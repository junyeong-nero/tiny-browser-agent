import {
  WebContentsView,
  type BrowserWindowConstructorOptions,
  type HandlerDetails,
  type WebContents,
  type WindowOpenHandlerResponse,
} from 'electron';


export type SameTabPopupProxyFactory = (
  options: BrowserWindowConstructorOptions,
  onPopupNavigate: (url: string) => void,
) => WebContents;


export function createSameTabWindowOpenHandler(
  loadURL: (url: string) => Promise<void>,
  createPopupProxy?: SameTabPopupProxyFactory,
): (details: Pick<HandlerDetails, 'url'>) => WindowOpenHandlerResponse {
  return ({ url }) => {
    if (url && url !== 'about:blank') {
      void loadURL(url);
      return { action: 'deny' };
    }

    if (createPopupProxy) {
      return {
        action: 'allow',
        createWindow: (options) =>
          createPopupProxy(options, (nextUrl) => {
            if (nextUrl && nextUrl !== 'about:blank') {
              void loadURL(nextUrl);
            }
          }),
      };
    }

    return { action: 'deny' };
  };
}


export function attachSameTabPopupHandling(browserSurfaceView: WebContentsView): {
  closeAllPopupProxies(): void;
} {
  const popupProxyViews = new Set<WebContentsView>();
  const closePopupProxyView = (popupProxyView: WebContentsView): void => {
    popupProxyViews.delete(popupProxyView);
    if (!popupProxyView.webContents.isDestroyed()) {
      popupProxyView.webContents.close();
    }
  };
  const loadURLInCurrentSurface = (url: string) => browserSurfaceView.webContents.loadURL(url);
  const createPopupProxy: SameTabPopupProxyFactory = (options, onPopupNavigate) => {
    const popupProxyView = new WebContentsView({ webPreferences: options.webPreferences });
    popupProxyViews.add(popupProxyView);
    popupProxyView.webContents.once('destroyed', () => {
      popupProxyViews.delete(popupProxyView);
    });
    popupProxyView.webContents.on('will-navigate', (event, popupUrl) => {
      event.preventDefault();
      onPopupNavigate(popupUrl);
      closePopupProxyView(popupProxyView);
    });
    popupProxyView.webContents.setWindowOpenHandler(
      createSameTabWindowOpenHandler(loadURLInCurrentSurface, createPopupProxy),
    );
    return popupProxyView.webContents;
  };

  browserSurfaceView.webContents.setWindowOpenHandler(
    createSameTabWindowOpenHandler(loadURLInCurrentSurface, createPopupProxy),
  );

  return {
    closeAllPopupProxies() {
      for (const popupProxyView of popupProxyViews) {
        closePopupProxyView(popupProxyView);
      }
    },
  };
}

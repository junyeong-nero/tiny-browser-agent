import { useCallback, useEffect, useState, type RefObject } from 'react';

import { getFocusShortcutRegion, type FocusRegion } from '../focus/focusManager';

interface UseFocusRegionsOptions {
  browserPaneRef: RefObject<HTMLDivElement>;
  verificationPanelRef: RefObject<HTMLDivElement>;
  chatInputRef: RefObject<HTMLInputElement>;
  focusBrowserSurface: () => Promise<void>;
}

export function useFocusRegions({
  browserPaneRef,
  verificationPanelRef,
  chatInputRef,
  focusBrowserSurface,
}: UseFocusRegionsOptions) {
  const [focusedRegion, setFocusedRegion] = useState<FocusRegion | null>(null);

  const focusBrowserPane = useCallback(() => {
    setFocusedRegion('browser');
    void focusBrowserSurface();
  }, [focusBrowserSurface]);

  const focusVerificationPanel = useCallback(() => {
    setFocusedRegion('verification');
    verificationPanelRef.current?.focus();
  }, [verificationPanelRef]);

  const focusChatInput = useCallback(() => {
    setFocusedRegion('chat');
    chatInputRef.current?.focus();
  }, [chatInputRef]);

  useEffect(() => {
    const browserElement = browserPaneRef.current;
    const verificationElement = verificationPanelRef.current;
    const chatElement = chatInputRef.current;

    const handleBrowserFocus = () => setFocusedRegion('browser');
    const handleVerificationFocus = () => setFocusedRegion('verification');
    const handleChatFocus = () => setFocusedRegion('chat');

    browserElement?.addEventListener('focusin', handleBrowserFocus);
    verificationElement?.addEventListener('focusin', handleVerificationFocus);
    chatElement?.addEventListener('focus', handleChatFocus);

    return () => {
      browserElement?.removeEventListener('focusin', handleBrowserFocus);
      verificationElement?.removeEventListener('focusin', handleVerificationFocus);
      chatElement?.removeEventListener('focus', handleChatFocus);
    };
  }, [browserPaneRef, chatInputRef, verificationPanelRef]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const region = getFocusShortcutRegion(event);
      if (!region) {
        return;
      }

      event.preventDefault();
      if (region === 'browser') {
        focusBrowserPane();
        return;
      }
      if (region === 'verification') {
        focusVerificationPanel();
        return;
      }
      focusChatInput();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [focusBrowserPane, focusChatInput, focusVerificationPanel]);

  return {
    focusedRegion,
    focusBrowserPane,
    focusVerificationPanel,
    focusChatInput,
  };
}

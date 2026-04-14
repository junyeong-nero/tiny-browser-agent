export type FocusRegion = 'browser' | 'verification' | 'chat';


interface FocusShortcutEvent {
  altKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey?: boolean;
  key: string;
}


export function getFocusShortcutRegion(event: FocusShortcutEvent): FocusRegion | null {
  const usesPrimaryModifier =
    !event.altKey &&
    !event.shiftKey &&
    ((event.ctrlKey && !event.metaKey) || (!event.ctrlKey && event.metaKey));
  const usesLegacyAltModifier =
    event.altKey &&
    !event.shiftKey &&
    !event.ctrlKey &&
    !event.metaKey;

  if (!usesPrimaryModifier && !usesLegacyAltModifier) {
    return null;
  }

  switch (event.key) {
    case '1':
      return 'browser';
    case '2':
      return 'verification';
    case '3':
      return 'chat';
    default:
      return null;
  }
}

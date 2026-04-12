export type FocusRegion = 'browser' | 'verification' | 'chat';


interface FocusShortcutEvent {
  altKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  key: string;
}


export function getFocusShortcutRegion(event: FocusShortcutEvent): FocusRegion | null {
  if (event.ctrlKey || event.metaKey || !event.altKey) {
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

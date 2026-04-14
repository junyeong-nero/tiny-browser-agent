export type FocusRegion = 'browser' | 'verification' | 'chat';

export interface FocusShortcutInput {
  alt: boolean;
  control: boolean;
  key: string;
  meta: boolean;
  shift: boolean;
  type?: string;
}

export function getFocusShortcutRegion(input: FocusShortcutInput): FocusRegion | null {
  if (input.type && input.type !== 'keyDown') {
    return null;
  }

  const usesPrimaryModifier =
    !input.alt &&
    !input.shift &&
    ((input.control && !input.meta) || (!input.control && input.meta));
  const usesLegacyAltModifier =
    input.alt &&
    !input.shift &&
    !input.control &&
    !input.meta;

  if (!usesPrimaryModifier && !usesLegacyAltModifier) {
    return null;
  }

  switch (input.key) {
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

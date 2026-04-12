import { describe, expect, it } from 'vitest';

import { getFocusShortcutRegion } from './focusManager';


describe('getFocusShortcutRegion', () => {
  it('maps Alt+1/2/3 to focus regions', () => {
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: false, key: '1' })).toBe('browser');
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: false, key: '2' })).toBe('verification');
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: false, key: '3' })).toBe('chat');
  });

  it('ignores unrelated or modified shortcuts', () => {
    expect(getFocusShortcutRegion({ altKey: false, ctrlKey: false, metaKey: false, key: '1' })).toBeNull();
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: true, metaKey: false, key: '1' })).toBeNull();
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: true, key: '1' })).toBeNull();
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: false, key: 'x' })).toBeNull();
  });
});

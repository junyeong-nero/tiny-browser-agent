import { describe, expect, it } from 'vitest';

import { getFocusShortcutRegion } from './focusManager';


describe('getFocusShortcutRegion', () => {
  it('maps Ctrl/Cmd+1/2/3 to focus regions', () => {
    expect(getFocusShortcutRegion({ altKey: false, ctrlKey: true, metaKey: false, shiftKey: false, key: '1' })).toBe('browser');
    expect(getFocusShortcutRegion({ altKey: false, ctrlKey: true, metaKey: false, shiftKey: false, key: '2' })).toBe('verification');
    expect(getFocusShortcutRegion({ altKey: false, ctrlKey: false, metaKey: true, shiftKey: false, key: '3' })).toBe('chat');
  });

  it('keeps Alt+1/2/3 as a legacy fallback', () => {
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, key: '1' })).toBe('browser');
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, key: '2' })).toBe('verification');
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: false, shiftKey: false, key: '3' })).toBe('chat');
  });

  it('ignores unrelated or modified shortcuts', () => {
    expect(getFocusShortcutRegion({ altKey: false, ctrlKey: false, metaKey: false, shiftKey: false, key: '1' })).toBeNull();
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: true, metaKey: false, shiftKey: false, key: '1' })).toBeNull();
    expect(getFocusShortcutRegion({ altKey: true, ctrlKey: false, metaKey: true, shiftKey: false, key: '1' })).toBeNull();
    expect(getFocusShortcutRegion({ altKey: false, ctrlKey: true, metaKey: false, shiftKey: true, key: '1' })).toBeNull();
    expect(getFocusShortcutRegion({ altKey: false, ctrlKey: false, metaKey: false, shiftKey: false, key: 'x' })).toBeNull();
  });
});

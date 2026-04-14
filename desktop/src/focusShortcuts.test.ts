import test from 'node:test';
import assert from 'node:assert/strict';

import { getFocusShortcutRegion } from './focusShortcuts';


test('maps Ctrl/Cmd+1/2/3 to focus regions', () => {
  assert.equal(
    getFocusShortcutRegion({ alt: false, control: true, key: '1', meta: false, shift: false, type: 'keyDown' }),
    'browser',
  );
  assert.equal(
    getFocusShortcutRegion({ alt: false, control: true, key: '2', meta: false, shift: false, type: 'keyDown' }),
    'verification',
  );
  assert.equal(
    getFocusShortcutRegion({ alt: false, control: false, key: '3', meta: true, shift: false, type: 'keyDown' }),
    'chat',
  );
});


test('keeps Alt+1/2/3 as a legacy fallback', () => {
  assert.equal(
    getFocusShortcutRegion({ alt: true, control: false, key: '1', meta: false, shift: false, type: 'keyDown' }),
    'browser',
  );
  assert.equal(
    getFocusShortcutRegion({ alt: true, control: false, key: '2', meta: false, shift: false, type: 'keyDown' }),
    'verification',
  );
  assert.equal(
    getFocusShortcutRegion({ alt: true, control: false, key: '3', meta: false, shift: false, type: 'keyDown' }),
    'chat',
  );
});


test('ignores unrelated or modified shortcuts', () => {
  assert.equal(
    getFocusShortcutRegion({ alt: false, control: false, key: '1', meta: false, shift: false, type: 'keyDown' }),
    null,
  );
  assert.equal(
    getFocusShortcutRegion({ alt: false, control: true, key: '1', meta: false, shift: true, type: 'keyDown' }),
    null,
  );
  assert.equal(
    getFocusShortcutRegion({ alt: true, control: true, key: '1', meta: false, shift: false, type: 'keyDown' }),
    null,
  );
  assert.equal(
    getFocusShortcutRegion({ alt: false, control: true, key: '1', meta: false, shift: false, type: 'keyUp' }),
    null,
  );
  assert.equal(
    getFocusShortcutRegion({ alt: false, control: true, key: 'x', meta: false, shift: false, type: 'keyDown' }),
    null,
  );
});

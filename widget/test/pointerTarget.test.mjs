import assert from 'node:assert/strict'
import test from 'node:test'
import { isInteractiveTarget, INTERACTIVE_SELECTOR } from '../src/renderer/src/ui/pointerTarget.mjs'

function targetWithInteractiveAncestor(isInteractive) {
  return {
    closest(selector) {
      assert.equal(selector, INTERACTIVE_SELECTOR)
      return isInteractive ? {} : null
    },
  }
}

test('captures input over the close button', () => {
  assert.equal(isInteractiveTarget(targetWithInteractiveAncestor(true)), true)
})

test('captures input over the character controls', () => {
  assert.equal(isInteractiveTarget(targetWithInteractiveAncestor(true)), true)
})

test('leaves non-interactive background click-through', () => {
  assert.equal(isInteractiveTarget(targetWithInteractiveAncestor(false)), false)
})

test('handles pointer events without a target', () => {
  assert.equal(isInteractiveTarget(null), false)
})

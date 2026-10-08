export const INTERACTIVE_SELECTOR = '[data-interactive]'

export function isInteractiveTarget(target) {
  return Boolean(target?.closest(INTERACTIVE_SELECTOR))
}

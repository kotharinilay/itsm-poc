/** Selector for elements that are focusable by default. Disabled and `tabindex="-1"` are excluded. */
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(',');

function isVisible(element: HTMLElement): boolean {
  // `offsetParent` is null for `display:none` subtrees; `position:fixed` needs the rect fallback.
  return element.offsetParent !== null || element.getClientRects().length > 0;
}

/** Focusable descendants of `root`, in document order. */
export function focusableWithin(root: HTMLElement): readonly HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) => isVisible(element) && element.getAttribute('aria-hidden') !== 'true',
  );
}

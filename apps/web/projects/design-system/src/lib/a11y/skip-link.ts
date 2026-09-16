import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * "Skip to main content" — the first tab stop on every surface.
 *
 * WCAG 2.2 Level AA (2.4.1 Bypass Blocks). It is visually hidden until focused, which is why it is
 * a component rather than a utility class: getting the reveal-on-focus wrong makes it useless to
 * sighted keyboard users, and that mistake is easy to repeat once per surface.
 */
@Component({
  selector: 'ds-skip-link',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './skip-link.html',
  styleUrl: './skip-link.css',
})
export class SkipLink {
  /** Id of the landmark to jump to. The host surface owns the element carrying it. */
  readonly targetId = input<string>('main-content');
  readonly label = input<string>('Skip to main content');
}

import { describe, expect, it } from 'vitest';

import { applyTheme, resolveInitialTheme } from '@/store/theme';

describe('theme utils', () => {
  it('returns stored theme when storage value is valid', () => {
    expect(resolveInitialTheme('dark', false)).toBe('dark');
    expect(resolveInitialTheme('light', true)).toBe('light');
  });

  it('falls back to system preference when storage value is invalid', () => {
    expect(resolveInitialTheme('invalid', true)).toBe('dark');
    expect(resolveInitialTheme('', false)).toBe('light');
  });

  it('applies theme to root element using data attribute and dark class', () => {
    const root = document.documentElement;
    applyTheme('dark', root);

    expect(root.dataset.theme).toBe('dark');
    expect(root.classList.contains('dark')).toBe(true);
    expect(root.style.colorScheme).toBe('dark');

    applyTheme('light', root);

    expect(root.dataset.theme).toBe('light');
    expect(root.classList.contains('dark')).toBe(false);
    expect(root.style.colorScheme).toBe('light');
  });
});

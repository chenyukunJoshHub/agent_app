export type ThemeMode = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'agent_app.theme_mode';

export function resolveInitialTheme(
  storageTheme: string | null,
  prefersDark: boolean,
): ThemeMode {
  if (storageTheme === 'light' || storageTheme === 'dark') {
    return storageTheme;
  }
  return prefersDark ? 'dark' : 'light';
}

export function applyTheme(theme: ThemeMode, root: HTMLElement): void {
  root.dataset.theme = theme;
  root.classList.toggle('dark', theme === 'dark');
  root.style.colorScheme = theme;
}

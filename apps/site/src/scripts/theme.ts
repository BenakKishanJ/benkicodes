import { themes, DEFAULT_THEME, type ThemeId } from '../lib/themes';
import { wipeCover, fxOn } from './pixelfx';

const THEME_KEY = 'benki-theme';
const FX_KEY = 'benki-fx';

export function currentTheme(): ThemeId {
  return (document.documentElement.dataset.theme as ThemeId) || DEFAULT_THEME;
}

/** Switch theme with a pixel-scatter wipe: blocks cover the screen, the theme swaps, blocks dissolve. */
export async function setTheme(id: string, animated = true): Promise<void> {
  const t = themes.find((x) => x.id === id) ?? themes[0];
  const root = document.documentElement;
  if (root.dataset.theme === t.id) return;
  const apply = () => {
    root.dataset.theme = t.id;
    try { localStorage.setItem(THEME_KEY, t.id); } catch { /* ignore */ }
    window.dispatchEvent(new CustomEvent('benki:theme', { detail: { id: t.id } }));
  };
  if (animated && fxOn()) {
    const reveal = await wipeCover(t.bg, t.accent);
    apply();
    await new Promise((r) => setTimeout(r, 60));
    await reveal();
  } else apply();
}

export function toggleEffects(): boolean {
  const root = document.documentElement;
  const next = root.dataset.fx === 'off' ? 'on' : 'off';
  root.dataset.fx = next;
  try { localStorage.setItem(FX_KEY, next); } catch { /* ignore */ }
  window.dispatchEvent(new CustomEvent('benki:fx', { detail: { on: next === 'on' } }));
  return next === 'on';
}

export const themeLabel = (id: string) => themes.find((t) => t.id === id)?.label ?? id;

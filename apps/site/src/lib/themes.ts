// Three Kanagawa themes. Colours live in global.css; this file is the JS-side registry.
// "bg" is the colour of the first (tone-a) section and is used by the pixel-wipe transition.
export type ThemeId = 'wave' | 'dragon' | 'lotus';
export interface ThemeDef {
  id: ThemeId;
  label: string;
  blurb: string;
  mode: 'dark' | 'light';
  bg: string;       // tone-a background
  alt: string;      // tone-b background
  accent: string;
  accent2: string;
}

export const DEFAULT_THEME: ThemeId = 'wave';

export const themes: ThemeDef[] = [
  { id: 'wave',   label: 'wave',   blurb: 'deep ink, crystal blue', mode: 'dark',  bg: '#1F1F28', alt: '#DCD7BA', accent: '#7E9CD8', accent2: '#957FB8' },
  { id: 'dragon', label: 'dragon', blurb: 'charcoal, moss green',   mode: 'dark',  bg: '#181616', alt: '#C5C9C5', accent: '#87A987', accent2: '#C4746E' },
  { id: 'lotus',  label: 'lotus',  blurb: 'warm paper, sakura pink', mode: 'light', bg: '#F2ECBC', alt: '#545464', accent: '#B35B79', accent2: '#4D699B' },
];

export const themeIds = themes.map((t) => t.id);

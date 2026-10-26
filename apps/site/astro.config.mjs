import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://benkicodes.pages.dev', // keep in sync with src/site.config.ts
  trailingSlash: 'always',
  integrations: [mdx(), sitemap(), react()],
  prefetch: true,
  vite: { plugins: [tailwindcss()] },
  markdown: {
    shikiConfig: {
      // One Shiki theme per site theme; global.css picks one by html[data-theme]
      themes: { wave: 'kanagawa-wave', dragon: 'kanagawa-dragon', lotus: 'kanagawa-lotus' },
      defaultColor: false,
      wrap: false,
    },
  },
});

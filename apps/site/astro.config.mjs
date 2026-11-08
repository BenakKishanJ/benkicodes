import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import { buildLastmodMap } from './sitemap-lastmod.mjs';

const lastmodMap = buildLastmodMap();

export default defineConfig({
  site: 'https://benkicodes.pages.dev', // keep in sync with src/site.config.ts
  trailingSlash: 'always',
  integrations: [
    mdx(),
    react(),
    // SE-4: accurate lastmod per content page; thin tag pages stay out.
    sitemap({
      filter: (page) =>
        !page.includes('/blog/tags/') && !page.includes('/404') && !page.includes('/admin/'),
      serialize(item) {
        const path = new URL(item.url).pathname;
        const lastmod = lastmodMap.get(path);
        return { ...item, lastmod, links: undefined };
      },
    }),
  ],
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

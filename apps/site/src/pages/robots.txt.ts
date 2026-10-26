import type { APIRoute } from 'astro';
import { siteConfig, indexing } from '../site.config';

// Indexing toggle (PRD 02 §7 SE-3):
//  off -> `Disallow: /` (staging)
//  on  -> allow all + Sitemap pointer (launch)
export const GET: APIRoute = () => {
  const body = indexing.on
    ? ['User-agent: *', 'Allow: /', '', `Sitemap: ${new URL('sitemap-index.xml', siteConfig.url).href}`].join('\n')
    : ['User-agent: *', 'Disallow: /'].join('\n');
  return new Response(`${body}\n`, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
};

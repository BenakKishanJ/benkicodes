// Single source of truth for branding, nav, ads, analytics and indexing.
// Nothing brand-specific should be hard-coded elsewhere (keeps the template sellable).

// Indexing is controlled by the PUBLIC_SITE_INDEXING env var at build time
// ('on' | 'off'). Anything other than 'on' means the site stays unindexable:
// a missing value must fail closed (PRD 02 §5.3, PRD 01 §5.2).
const indexingRaw = String(import.meta.env.PUBLIC_SITE_INDEXING ?? '').toLowerCase();
export const indexing =
  {
    on: indexingRaw === 'on',
    off: indexingRaw !== 'on',
  } as const;

// Placeholder contact details — replace before launch.
export const siteConfig = {
  name: 'BenKi Codes',
  shortName: 'benki',
  tagline: 'Roadmaps and build-along guides for AI-era full-stack developers.',
  description:
    'Source-cited, human-reviewed tech articles and interactive learning roadmaps with quizzes.',
  url: 'https://benkicodes.pages.dev', // switch to your custom domain before applying for AdSense
  locale: 'en',
  author: {
    name: 'Ben',
    email: 'you@example.com', // TODO
    github: 'https://github.com/your-username', // TODO
    linkedin: 'https://www.linkedin.com/in/your-handle', // TODO
  },
  nav: [
    { label: 'home', href: '/' },
    { label: 'blog', href: '/blog/' },
    { label: 'roadmaps', href: '/roadmaps/' },
    { label: 'projects', href: '/projects/' },
    { label: 'about', href: '/about/' },
  ],
  footerLinks: [
    { label: 'editorial', href: '/editorial-policy/' },
    { label: 'privacy', href: '/privacy/' },
    { label: 'terms', href: '/terms/' },
    { label: 'contact', href: '/contact/' },
    { label: 'rss', href: '/rss.xml' },
  ],
  aiDisclosure:
    'Drafted with AI assistance from the sources listed below, then reviewed and edited by the author.',
  ads: {
    enabled: false, // flip to true only after AdSense approval + consent banner is in place
    client: 'ca-pub-0000000000000000',
    slots: { 'in-article': '0000000000', 'sidebar': '0000000000' } as Record<string, string>,
  },
  analytics: {
    // Cloudflare Web Analytics beacon token. Leave empty to disable.
    cloudflareToken: '',
  },
  features: { commandPalette: true, effects: true },
} as const;

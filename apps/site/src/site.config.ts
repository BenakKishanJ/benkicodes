// Single source of truth for branding, nav, ads and analytics.
// Nothing brand-specific should be hard-coded elsewhere (keeps the template sellable).

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

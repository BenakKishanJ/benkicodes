import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { siteConfig } from '../../site.config';
import { getModules, getRoadmaps, roadmapSlug, moduleSlug } from '../../lib/content';

// SE-5: one item per published part, newest reviewed first.
export async function GET(context: APIContext) {
  const modules = await getModules();
  const roadmaps = await getRoadmaps();
  const items = modules
    .sort((a, b) => b.data.lastReviewed.valueOf() - a.data.lastReviewed.valueOf())
    .map((m) => {
      const rs = roadmapSlug(m.id);
      const course = roadmaps.find((r) => roadmapSlug(r.id) === rs);
      return {
        title: `${m.data.title} · ${course?.data.title ?? rs}`,
        description: `${course?.data.title ?? rs} roadmap — part ${m.data.order}: ${m.data.objectives[0]}`,
        pubDate: m.data.lastReviewed,
        link: `/roadmaps/${rs}/${moduleSlug(m.id)}/`,
        categories: course?.data.tags ?? [],
      };
    });
  return rss({
    title: `${siteConfig.name} — roadmaps`,
    description: `${siteConfig.tagline} Feed of published course parts.`,
    site: context.site ?? siteConfig.url,
    items,
    customData: '<language>en</language>',
  });
}

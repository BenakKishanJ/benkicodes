// SE-6: one prerendered 1200x630 PNG per page. BaseLayout falls back to
// /og/<pathname>.png for every non-home page, so getStaticPaths must cover
// exactly the same route list (check-dist verifies the pairing).
import type { APIRoute, GetStaticPaths } from 'astro';
import { generateOg } from '../../lib/og';
import { getPosts, getRoadmaps, getModules, getProjects, roadmapSlug, moduleSlug } from '../../lib/content';

interface OgProps {
  title: string;
  description?: string;
  label?: string;
  [key: string]: unknown;
}

export const getStaticPaths = (async () => {
  const [posts, roadmaps, allModules, projects] = await Promise.all([
    getPosts(),
    getRoadmaps(),
    getModules(),
    getProjects(),
  ]);

  const paths: { params: { route: string }; props: OgProps }[] = [
    // Static pages first (names mirror each page's BaseLayout title).
    { params: { route: '404' }, props: { title: 'Page not found', description: 'The page you entered does not exist here.', label: '404' } },
    { params: { route: 'about' }, props: { title: 'About', description: 'Who writes this site, how, and why.', label: 'about' } },
    { params: { route: 'contact' }, props: { title: 'Contact', description: 'Email for corrections and collaboration, GitHub for code, LinkedIn for professional mail.', label: 'contact' } },
    { params: { route: 'privacy' }, props: { title: 'Privacy policy', description: 'What data this site collects, what it stores, and how to contact the owner.', label: 'policy' } },
    { params: { route: 'terms' }, props: { title: 'Terms + disclaimer', description: 'Terms of use: educational disclaimer, AI-assistance disclosure, licensing.', label: 'policy' } },
    { params: { route: 'editorial-policy' }, props: { title: 'Editorial policy', description: 'How articles and roadmaps are researched, written with AI assistance, reviewed and corrected.', label: 'policy' } },
    { params: { route: 'blog' }, props: { title: 'Blog', description: 'Guides, tooling notes and news for full-stack and AI engineers.', label: 'blog' } },
    { params: { route: 'roadmaps' }, props: { title: 'Roadmaps', description: 'Structured learning paths with a quiz at the end of every part.', label: 'roadmaps' } },
    { params: { route: 'projects' }, props: { title: 'Projects', description: 'Things built and being built: what they do and what was learned.', label: 'projects' } },
  ];

  // Blog pagination roots: /blog/2/... ([...page] rest param).
  const pageSize = 9;
  const pageCount = Math.ceil(posts.length / pageSize);
  for (let pageIdx = 2; pageIdx <= pageCount; pageIdx++) {
    paths.push({ params: { route: `blog/${pageIdx}` }, props: { title: `Blog, page ${pageIdx}`, description: 'Guides, tooling notes and news for full-stack and AI engineers.', label: 'blog' } });
  }

  for (const p of posts) {
    paths.push({
      params: { route: `blog/${p.id}` },
      props: { title: p.data.title, description: p.data.description, label: p.data.category },
    });
  }

  for (const tag of [...new Set(posts.flatMap((p) => p.data.tags))].sort()) {
    paths.push({
      params: { route: `blog/tags/${tag}` },
      props: { title: `Posts tagged ${tag}`, description: `All posts, guides and news tagged ${tag}.`, label: 'tag' },
    });
  }

  for (const r of roadmaps) {
    const rs = roadmapSlug(r.id);
    paths.push({ params: { route: `roadmaps/${rs}` }, props: { title: r.data.title, description: r.data.description, label: `roadmap · ${r.data.level}` } });
  }

  for (const m of allModules) {
    const rs = roadmapSlug(m.id);
    const siblings = allModules.filter((x) => roadmapSlug(x.id) === rs);
    const i = siblings.findIndex((s) => s.id === m.id);
    const course = roadmaps.find((r) => roadmapSlug(r.id) === rs);
    paths.push({
      params: { route: `roadmaps/${rs}/${moduleSlug(m.id)}` },
      props: {
        title: m.data.title,
        description: course ? `${course.data.title} - part ${i + 1} of ${siblings.length}.` : m.data.objectives[0],
        label: `part ${i + 1}/${siblings.length}`,
      },
    });
  }

  for (const project of projects) {
    paths.push({
      params: { route: `projects/${project.id}` },
      props: { title: project.data.title, description: project.data.summary, label: 'project' },
    });
  }

  return paths;
}) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) => {
  const png = await generateOg(props as OgProps);
  return new Response(new Uint8Array(png), {
    headers: { 'content-type': 'image/png', 'cache-control': 'public, max-age=31536000, immutable' },
  });
};

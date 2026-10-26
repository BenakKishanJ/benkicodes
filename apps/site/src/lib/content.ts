import { getCollection, type CollectionEntry } from 'astro:content';

const visible = ({ data }: { data: { draft: boolean } }) => (import.meta.env.PROD ? !data.draft : true);

export async function getPosts(): Promise<CollectionEntry<'blog'>[]> {
  const posts = (await getCollection('blog', visible)) as CollectionEntry<'blog'>[];
  return posts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
}

export async function getRoadmaps(): Promise<CollectionEntry<'roadmaps'>[]> {
  const items = (await getCollection('roadmaps', visible)) as CollectionEntry<'roadmaps'>[];
  return items.sort((a, b) => b.data.lastReviewed.valueOf() - a.data.lastReviewed.valueOf());
}

/** The roadmap slug is always the first path segment of the entry id. */
export const roadmapSlug = (id: string) => id.split('/')[0];
export const moduleSlug = (id: string) => id.split('/').pop()!;

export async function getModules(roadmap?: string): Promise<CollectionEntry<'modules'>[]> {
  const all = (await getCollection('modules', visible)) as CollectionEntry<'modules'>[];
  return all
    .filter((m) => (roadmap ? roadmapSlug(m.id) === roadmap : true))
    .sort((a, b) => a.data.order - b.data.order);
}

export async function getProjects(): Promise<CollectionEntry<'projects'>[]> {
  const items = await getCollection('projects');
  return items.sort((a, b) => a.data.order - b.data.order);
}

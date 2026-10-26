import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import {
  blogSchema,
  roadmapSchema,
  moduleSchema,
  projectSchema,
} from '@benki/content-schema';

const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: blogSchema,
});

// One folder per roadmap: roadmaps/<slug>/index.md  +  roadmaps/<slug>/modules/*.md(x)
const roadmaps = defineCollection({
  loader: glob({ pattern: '*/index.{md,mdx}', base: './src/content/roadmaps' }),
  schema: roadmapSchema,
});

const modules = defineCollection({
  loader: glob({ pattern: '*/modules/*.{md,mdx}', base: './src/content/roadmaps' }),
  schema: moduleSchema,
});

const projects = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/projects' }),
  schema: projectSchema,
});

export const collections = { blog, roadmaps, modules, projects };

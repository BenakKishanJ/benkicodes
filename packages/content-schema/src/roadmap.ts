import { z } from 'zod';
import { githubUrl, quizQuestion, source } from './common.js';

// Roadmap (course) index frontmatter (02-prd §5.2)
export const roadmapSchema = z.object({
  title: z.string(),
  description: z.string().max(160),
  level: z.enum(['beginner', 'intermediate', 'advanced']),
  estimatedHours: z.number(),
  prerequisites: z.array(z.string()).default([]),
  outcomes: z.array(z.string()).min(3),
  tags: z.array(z.string()).default([]),
  // Hands-on course status and planned-but-unpublished parts
  status: z.enum(['in-progress', 'complete']).default('in-progress'),
  planned: z
    .array(
      z.object({
        slug: z.string().min(1),
        title: z.string(),
        estimatedMinutes: z.number(),
      }),
    )
    .default([]),
  // The guided project learners build (RM-2)
  project: z.object({
    repo: githubUrl,
    defaultBranch: z.string().default('main'),
    template: z.boolean().default(false),
    license: z.string().optional(),
    stack: z.array(z.string()).default([]),
    summary: z.string().max(240),
  }),
  // Courses/roadmaps/articles that shaped the structure (RM-4)
  inspiredBy: z
    .array(
      z.object({
        title: z.string(),
        url: z.url(),
        author: z.string().optional(),
        note: z.string().optional(),
      }),
    )
    .default([]),
  lastReviewed: z.coerce.date(),
  version: z.string().default('1.0'),
  draft: z.boolean().default(false),
  featured: z.boolean().default(false),
  pipelineRunId: z.string().optional(),
});

// A single part (module) frontmatter (02-prd §5.3)
export const moduleSchema = z.object({
  title: z.string(),
  order: z.number(),
  estimatedMinutes: z.number(),
  objectives: z.array(z.string()).min(2),
  // Official docs cited in the lesson (RM-15)
  sources: z.array(source).min(1),
  // Curated links (RM-14)
  resources: z
    .array(
      z.object({
        title: z.string(),
        url: z.url(),
        type: z.enum(['docs', 'video', 'article', 'repo', 'interactive', 'book']),
        why: z.string().max(200),
        illustrated: z.boolean().default(false),
      }),
    )
    .default([]),
  // Ties the lesson to the project repo (RM-12)
  code: z.object({
    startTag: z.string().min(1),
    endTag: z.string().min(1),
    compareUrl: githubUrl,
    treeUrl: githubUrl,
    commits: z
      .array(
        z.object({
          sha: z.string().min(7),
          message: z.string(),
          url: githubUrl,
        }),
      )
      .min(1),
    files: z.array(z.string()),
  }),
  quiz: z.array(quizQuestion).min(3),
  lastReviewed: z.coerce.date(),
  draft: z.boolean().default(false),
  pipelineRunId: z.string().optional(),
});

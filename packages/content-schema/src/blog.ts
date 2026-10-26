import { z } from 'zod';
import { source } from './common.js';

// Blog post frontmatter (02-prd §5.1)
export const blogSchema = z.object({
  title: z.string().max(70),
  description: z.string().min(70).max(160),
  pubDate: z.coerce.date(),
  updatedDate: z.coerce.date().optional(),
  lastReviewed: z.coerce.date(),
  tags: z.array(z.string()).min(1).max(6),
  category: z.enum(['news', 'guide', 'tutorial', 'opinion', 'tooling']),
  cover: z.object({ src: z.string(), alt: z.string() }).optional(),
  // Links the post to a course part it supports (BL-4 callout)
  relatedPart: z
    .object({ course: z.string().min(1), part: z.string().min(1) })
    .optional(),
  draft: z.boolean().default(false),
  featured: z.boolean().default(false),
  sources: z.array(source).min(1),
  aiAssisted: z.boolean().default(true),
  reviewedBy: z.string().default('Ben'),
  pipelineRunId: z.string().optional(),
  canonical: z.url().optional(),
});

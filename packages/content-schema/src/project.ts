import { z } from 'zod';

// Portfolio project frontmatter
export const projectSchema = z.object({
  title: z.string(),
  summary: z.string().max(200),
  status: z.enum(['active', 'shipped', 'archived']),
  stack: z.array(z.string()),
  repo: z.url().optional(),
  demo: z.url().optional(),
  featured: z.boolean().default(false),
  order: z.number().default(100),
  startDate: z.coerce.date(),
});

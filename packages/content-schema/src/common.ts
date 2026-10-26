// Shared schemas: referenced by more than one collection.
import { z } from 'zod';

export const source = z.object({
  title: z.string(),
  url: z.url(),
  publisher: z.string().optional(),
  accessed: z.coerce.date().optional(),
});

export const quizQuestion = z.object({
  id: z.string(),
  question: z.string(),
  type: z.enum(['single', 'multi']).default('single'),
  options: z.array(z.object({ id: z.string(), text: z.string() })).min(3).max(6),
  correct: z.array(z.string()).min(1),
  explanation: z.string(),
  difficulty: z.enum(['easy', 'medium', 'hard']).default('medium'),
  hint: z.string().optional(),
});

export const githubUrl = z.url().refine((u) => u.startsWith('https://github.com/'), {
  message: 'must be a GitHub URL',
});

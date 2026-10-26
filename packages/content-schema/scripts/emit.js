// Emits JSON Schema files for the Python pipeline (03-prd §5.3).
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { z } from 'zod';
import { blogSchema, roadmapSchema, moduleSchema, projectSchema } from '../dist/index.js';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, '..', 'dist');
mkdirSync(outDir, { recursive: true });

const targets = {
  'blog.schema.json': blogSchema,
  'roadmap.schema.json': roadmapSchema,
  'module.schema.json': moduleSchema,
  'project.schema.json': projectSchema,
};

for (const [name, schema] of Object.entries(targets)) {
  const json = z.toJSONSchema(/** @type {import('zod').ZodType} */ (schema), {
    target: 'draft-7',
    io: 'input',
    // z.coerce.date() ends as a ZodDate, which JSON Schema has no native type
    // for. The pipeline frontmatter it validates is YAML, so coerce inputs are
    // strings: emit date-time with format for those sites.
    unrepresentable: ({ zodSchema }) =>
      zodSchema._zod?.def?.type === 'date'
        ? { type: 'string', format: 'date-time' }
        : { type: 'any' },
  });
  writeFileSync(join(outDir, name), JSON.stringify(json, null, 2) + '\n');
  console.log(`wrote dist/${name}`);
}

// Read-only list of what is live (GET /library): every post in the site repo's
// blog dir, with draft state and its frontmatter summary.
import { fmtTs } from '../api';
import { Chip, Panel } from '../ui';
import type { LibraryItem } from '../types';

export default function Library({ items }: { items: LibraryItem[] }) {
  return (
    <Panel title="Library" id="library-h" right={<span className="meta">{items.length} filed</span>}>
      {items.length === 0 && <p className="meta">Nothing in the blog directory yet.</p>}
      <ul className="my-2">
        {items.map((i) => (
          <li key={i.slug} className="row flex flex-wrap items-center gap-x-6 gap-y-2 px-3 py-4 text-[13px]">
            <Chip status={i.draft ? 'draft' : 'published'}>{i.draft ? 'draft' : 'live'}</Chip>
            <span className="text-fg">{i.title}</span>
            <a className="underline decoration-dashed underline-offset-4 hover:text-accent"
               href={`/blog/${i.slug}/`} rel="noopener noreferrer" target="_blank">/{i.slug}</a>
            <span className="meta">{i.category} · {i.tags.slice(0, 3).map((t: string) => `#${t}`).join(' ')}</span>
            {i.pubDate && <span className="meta ml-auto">{fmtTs(i.pubDate)}</span>}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

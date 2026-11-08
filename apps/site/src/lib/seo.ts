// SEO helpers (PRD 02 §7). BaseLayout.astro is the only place that emits
// head tags; pages compute everything through these helpers.
import { siteConfig } from '../site.config';

export interface MetaInput {
  title: string;
  description: string;
  /** Absolute canonical URL, or the page pathname to build one from. */
  canonical?: string;
  path?: string;
  type?: 'website' | 'article';
  publishedTime?: Date;
  modifiedTime?: Date;
  image?: string;
  noindex?: boolean;
  indexingOn: boolean;
}

export interface Meta {
  fullTitle: string;
  description: string;
  canonicalUrl: string;
  imageUrl: string;
  type: 'website' | 'article';
  robots: string;
  publishedTime?: Date;
  modifiedTime?: Date;
}

// SE-1: titles land around 60 chars (site suffix included);
// SE-12: staging builds are noindex no matter the page.
export function buildMeta(input: MetaInput): Meta {
  const path = input.path ?? '/';
  const fullTitle =
    path === '/' ? `${siteConfig.name}: ${siteConfig.tagline}` : `${input.title} | ${siteConfig.name}`;
  const canonicalUrl = input.canonical ?? new URL(input.path ?? '/', siteConfig.url).href;
  const imageUrl = new URL(input.image ?? '/og-default.png', siteConfig.url).href;
  const noindex = !input.indexingOn || input.noindex === true;
  const robots = noindex ? 'noindex, follow, max-image-preview:large' : 'max-image-preview:large';
  return {
    fullTitle,
    description: input.description,
    canonicalUrl,
    imageUrl,
    type: input.type ?? 'website',
    robots,
    publishedTime: input.publishedTime,
    modifiedTime: input.modifiedTime,
  };
}

export interface ArticleInput {
  headline: string;
  description: string;
  url: string;
  datePublished?: Date;
  dateModified: Date;
  author?: { name: string; url?: string };
  image?: string;
  keywords?: string[];
  /** BlogPosting marks a dated blog post; plain Article covers course pages. */
  type?: 'BlogPosting' | 'Article';
  publisher?: boolean;
}

// SE-7: visible-content only; Course/FAQPage/HowTo are never emitted here.
export function articleJsonLd(input: ArticleInput): Record<string, unknown> {
  const author = { '@type': 'Person', name: input.author?.name ?? siteConfig.author.name, ...(input.author?.url ? { url: input.author.url } : {}) };
  const ld: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': input.type ?? 'Article',
    headline: input.headline,
    description: input.description,
    mainEntityOfPage: input.url,
    dateModified: input.dateModified.toISOString(),
    author,
  };
  if (input.datePublished) ld.datePublished = input.datePublished.toISOString();
  if (input.image) ld.image = input.image;
  if (input.keywords && input.keywords.length > 0) ld.keywords = input.keywords.join(', ');
  if (input.publisher !== false && input.type !== 'BlogPosting') {
    ld.publisher = { '@type': 'Person', name: siteConfig.author.name };
  }
  return ld;
}

export interface Crumb {
  name: string;
  item?: string;
}

/** SE-7/SE-8: BreadcrumbList JSON-LD from a list of crumbs. */
export function breadcrumbJsonLd(crumbs: Crumb[]): Record<string, unknown> {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: crumbs.map((c, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: c.name,
      ...(c.item ? { item: c.item } : {}),
    })),
  };
}

// SE-7: Person markup for the author (About page, used inline elsewhere too).
export function personJsonLd(author: {
  name: string;
  email?: string;
  github?: string;
  linkedin?: string;
  aboutUrl: string;
}): Record<string, unknown> {
  const sameAs = [author.github, author.linkedin].filter((u): u is string => Boolean(u));
  return {
    '@context': 'https://schema.org',
    '@type': 'Person',
    name: author.name,
    url: author.aboutUrl,
    ...(sameAs.length > 0 ? { sameAs } : {}),
  };
}

/** SE-9: URL helper — join a path onto the site root. */
export const siteUrl = (path: string) => new URL(path, siteConfig.url).href;

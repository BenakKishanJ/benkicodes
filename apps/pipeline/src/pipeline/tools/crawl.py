"""Bounded same-domain crawl for the docs map (03-prd §7.3 `seed_docs`).

Fetches the official-docs URLs the user gives, follows same-domain links one
level (bounded), and returns page texts for the docs cache. Reuses ingest's
fetch/robots/injection hygiene; treats everything fetched as untrusted.
"""
from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

from .ingest import IngestError, UA, fetch_url, is_public_url, robots_allowed

SKIP_EXT = re.compile(r"\.(pdf|zip|gz|png|jpe?g|gif|svg|ico|webp|mp4|css|js|woff2?|xml|json|toml|yml)$", re.I)
_A_LINK = re.compile(r"""<a\b[^>]*href=["']([^"']+)["']""", re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_IMG = re.compile(r"<img\b", re.I)

ASSET_HINTS = ("#", "mailto:", "tel:", "javascript:")


def normalize(url: str) -> str:
    url, _ = urldefrag(url.strip())
    return url if not re.match(r"https?://[^/]+/$", url) else url.rstrip("/")


def _extract_links(base_url: str, html: str) -> list[str]:
    origin = "{0.scheme}://{0.netloc}".format(urlparse(base_url))
    out = []
    for href in _A_LINK.findall(html):
        if href.startswith(ASSET_HINTS) or SKIP_EXT.search(href.split("?")[0]):
            continue
        absu = urljoin(base_url, href)
        p = urlparse(absu)
        if p.scheme not in ("http", "https") or f"{p.scheme}://{p.netloc}" != origin:
            continue  # one level, same domain only
        out.append(normalize(absu))
    return list(dict.fromkeys(out))


def fetch_html(url: str, timeout: float, allow_private: bool = False) -> str:
    """Raw HTML for link extraction; raises IngestError like fetch_url."""
    if not allow_private and not is_public_url(url):
        raise IngestError("blocked: not a public http(s) address")
    r = httpx.get(url, timeout=timeout, headers={"User-Agent": UA}, follow_redirects=True)
    if r.status_code >= 400:
        raise IngestError(f"HTTP {r.status_code}")
    ct = r.headers.get("content-type", "")
    if "html" not in ct and (r.content[:1] not in (b"<",)):
        raise IngestError(f"not an html page ({ct or 'unknown type'})")
    return r.text


def crawl_docs(seed_urls: list[str], timeout: float = 15.0, max_pages: int = 30,
               allow_private: bool = False) -> tuple[list[dict], list[str]]:
    """Fetch seeds + up to `max_pages` same-domain links, one level deep.

    Returns (pages, skip_notes): pages = [{title, url, text, chars, has_images}],
    skip_notes = human-readable reasons for skipped seeds (fed to the run log).
    """
    pages: dict[str, dict] = {}
    skip: list[str] = []
    queue = [normalize(u) for u in seed_urls]
    seeds = set(queue)
    crawled_domains: set[str] = set()

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in pages or not is_public_url(url) or not robots_allowed(url):
            if url in seeds and url not in pages:
                skip.append(f"{url}: unfetchable or disallowed")
            continue
        try:
            html = fetch_html(url, timeout, allow_private)
            title, text = fetch_url(url, timeout, allow_private)
        except (IngestError, httpx.HTTPError, OSError, ValueError) as e:
            if url in seeds:
                skip.append(f"{url}: {type(e).__name__}: {e}")
            continue
        text = text[:60_000]
        pages[url] = {"title": (title or _title_from_html(html, url)), "url": url,
                      "text": text, "chars": len(text), "has_images": bool(_IMG.search(html))}
        origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if url in seeds and len(pages) < max_pages and origin not in crawled_domains:
            crawled_domains.add(origin)  # one level down per seed domain, bounded
            fresh = [u for u in _extract_links(url, html) if u not in pages]
            queue.extend(fresh[: max_pages * 2])
    ordered = [pages[u] for u in list(pages)]
    return ordered, skip


def _title_from_html(html: str, url: str) -> str:
    m = _TITLE.search(html)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()[:120]
    return url

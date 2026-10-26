"""Fetching and cleaning source material. Everything here treats input as untrusted."""
from __future__ import annotations
import ipaddress, re, socket
from functools import lru_cache
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import httpx

UA = "BenKiContentBot/0.1 (+personal research assistant)"
MAX_BYTES = 3_000_000

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above)",
    r"you are now\b", r"new instructions?:", r"system prompt", r"<\|?im_start\|?>", r"\bassistant:\s", r"developer message",
    r"do not tell the user", r"reveal your (instructions|prompt)",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]


class IngestError(Exception):
    pass


def scan_injection(text: str) -> list[str]:
    return sorted({m.group(0).lower() for rx in _INJ for m in [rx.search(text)] if m})


def clean_text(text: str, limit: int) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def is_public_url(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


@lru_cache(maxsize=64)
def _robots(origin: str) -> RobotFileParser | None:
    rp = RobotFileParser()
    try:
        r = httpx.get(urljoin(origin, "/robots.txt"), timeout=5, headers={"User-Agent": UA}, follow_redirects=True)
        if r.status_code >= 400:
            return None
        rp.parse(r.text.splitlines())
        return rp
    except Exception:
        return None


def robots_allowed(url: str) -> bool:
    p = urlparse(url)
    rp = _robots(f"{p.scheme}://{p.netloc}")
    return True if rp is None else rp.can_fetch(UA, url)


def pdf_to_text(data: bytes, max_pages: int = 40) -> str:
    import fitz  # pymupdf
    with fitz.open(stream=data, filetype="pdf") as doc:
        return "\n\n".join(page.get_text() for page, _ in zip(doc, range(max_pages)))


def fetch_url(url: str, timeout: float = 15.0, allow_private: bool = False) -> tuple[str, str]:
    """Returns (title, main_text). Raises IngestError with a human-readable reason."""
    if not allow_private and not is_public_url(url):
        raise IngestError("blocked: not a public http(s) address")
    if not robots_allowed(url):
        raise IngestError("blocked by robots.txt")
    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True, headers={"User-Agent": UA}, max_redirects=5) as r:
            if r.status_code >= 400:
                raise IngestError(f"HTTP {r.status_code}")
            ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype not in ("text/html", "application/xhtml+xml", "text/plain", "text/markdown", "application/pdf"):
                raise IngestError(f"unsupported content type: {ctype or 'unknown'}")
            buf = bytearray()
            for chunk in r.iter_bytes():
                buf.extend(chunk)
                if len(buf) > MAX_BYTES:
                    raise IngestError("page too large")
            raw, encoding = bytes(buf), r.encoding or "utf-8"
    except httpx.HTTPError as e:
        raise IngestError(f"network error: {type(e).__name__}") from e

    if ctype == "application/pdf":
        return urlparse(url).path.rsplit("/", 1)[-1] or url, pdf_to_text(raw)
    html = raw.decode(encoding, errors="replace")
    if ctype.startswith("text/plain") or ctype == "text/markdown":
        return url, html
    import trafilatura
    text = trafilatura.extract(html, include_comments=False, include_tables=True, favor_precision=True) or ""
    meta = trafilatura.extract_metadata(html)
    title = (meta.title if meta and meta.title else "") or url
    if len(text) < 200:
        raise IngestError("could not extract readable text")
    return title, text

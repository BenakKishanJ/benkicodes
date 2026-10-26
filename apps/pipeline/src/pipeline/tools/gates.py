"""Deterministic quality gates run on every draft before the human sees it.
Each gate returns {name, status: pass|warn|fail, detail}. Any 'fail' blocks publishing unless the author overrides."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import httpx

CITE_RE = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
CODE_RE = re.compile(r"```.*?```", re.DOTALL)
QUOTE_RE = re.compile(r"[\"“]([^\"”\n]{12,})[\"”]")


def cited_ids(md: str) -> list[str]:
    out: list[str] = []
    for m in CITE_RE.finditer(md):
        for sid in re.split(r"\s*,\s*", m.group(1)):
            if sid not in out:
                out.append(sid)
    return out


def _tokens(text: str) -> list[str]:
    text = CODE_RE.sub(" ", text)
    text = CITE_RE.sub(" ", text)
    return re.findall(r"[a-z0-9']+", text.lower())


def shingles(text: str, n: int = 8) -> set[tuple[str, ...]]:
    t = _tokens(text)
    return {tuple(t[i:i + n]) for i in range(max(0, len(t) - n + 1))}


def similarity(draft: str, source_text: str) -> float:
    d = shingles(draft)
    if not d:
        return 0.0
    return len(d & shingles(source_text)) / len(d)


def word_count(md: str) -> int:
    return len(_tokens(md))


def gate(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def check_links(urls: list[str], timeout: float = 6.0) -> list[tuple[str, str]]:
    def probe(u: str) -> tuple[str, str] | None:
        try:
            r = httpx.head(u, timeout=timeout, follow_redirects=True, headers={"User-Agent": "BenKiContentBot/0.1"})
            if r.status_code in (405, 403, 501):
                r = httpx.get(u, timeout=timeout, follow_redirects=True, headers={"User-Agent": "BenKiContentBot/0.1"})
            return None if r.status_code < 400 else (u, f"HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001 any probe failure is just a warn
            return (u, type(e).__name__)
    with ThreadPoolExecutor(max_workers=6) as ex:
        return [x for x in ex.map(probe, urls[:20]) if x]


def run_gates(*, draft: str, sources: list[dict], critique: dict | None, frontmatter_error: str | None,
              banned: list[str], max_similarity: float, length_range: tuple[int, int], check_urls: bool = True) -> list[dict]:
    by_id = {s["id"]: s for s in sources}
    results: list[dict] = []

    results.append(gate("schema", "fail" if frontmatter_error else "pass",
                        frontmatter_error or "metadata matches the site's content schema"))

    cites = cited_ids(draft)
    unknown = [c for c in cites if c not in by_id]
    no_url = [c for c in cites if c in by_id and not by_id[c].get("url")]
    if unknown:
        results.append(gate("citations", "fail", f"cites unknown sources: {', '.join(unknown)}"))
    elif not cites:
        results.append(gate("citations", "fail", "no citations found; every factual claim needs a [S#] marker"))
    elif no_url:
        names = ", ".join(f'{c} ("{by_id[c]["title"]}")' for c in no_url)
        results.append(gate("citations", "fail", f"cited sources without a URL: {names}. Add a URL to that source, or remove its citations."))
    else:
        results.append(gate("citations", "pass", f"{len(cites)} sources cited"))

    sections = re.split(r"(?m)^## ", draft)[1:]
    bare = [s.splitlines()[0] for s in sections if not CITE_RE.search(s)]
    results.append(gate("section coverage", "warn" if bare else "pass",
                        f"sections without any citation: {', '.join(bare)}" if bare else "every section cites a source"))

    uns = (critique or {}).get("unsupported_claims", [])
    high = [i for i in (critique or {}).get("issues", []) if i["severity"] == "high"]
    if uns:
        results.append(gate("unsupported claims", "fail" if len(uns) >= 3 or high else "warn", f"{len(uns)} flagged by the critic: " + "; ".join(uns[:4])))
    else:
        results.append(gate("unsupported claims", "pass", "the critic found none"))

    worst, worst_id = 0.0, ""
    for sid in cites or list(by_id):
        if sid in by_id:
            r = similarity(draft, by_id[sid]["text"])
            if r > worst:
                worst, worst_id = r, sid
    results.append(gate("similarity", "fail" if worst > max_similarity else "pass",
                        f"highest overlap with {worst_id or 'any source'}: {worst:.0%} (limit {max_similarity:.0%})"))

    quotes = [q for q in QUOTE_RE.findall(draft)]
    long_q = [q for q in quotes if len(q.split()) > 15]
    if long_q:
        results.append(gate("quotes", "fail", f"{len(long_q)} quote(s) longer than 15 words; paraphrase instead"))
    elif len(quotes) > 4:
        results.append(gate("quotes", "warn", f"{len(quotes)} quotes; keep them rare"))
    else:
        results.append(gate("quotes", "pass", f"{len(quotes)} short quote(s)"))

    low = draft.lower()
    hits = [b for b in banned if b and b.lower() in low]
    results.append(gate("filler phrases", "warn" if hits else "pass", ("found: " + ", ".join(hits)) if hits else "none of the banned phrases"))

    wc = word_count(draft)
    lo, hi = length_range
    results.append(gate("length", "pass" if lo * 0.7 <= wc <= hi * 1.3 else "warn", f"{wc} words (target {lo}-{hi})"))

    problems = []
    if re.search(r"(?m)^# [^#]", draft):
        problems.append("contains an H1 (the page already has one)")
    if len(re.findall(r"(?m)^## ", draft)) < 2:
        problems.append("fewer than two H2 sections")
    fences = re.findall(r"(?m)^```(.*)$", draft)
    opening = fences[::2]
    if any(not o.strip() for o in opening):
        problems.append("a code block has no language tag")
    results.append(gate("structure", "warn" if problems else "pass", "; ".join(problems) or "headings and code blocks look right"))

    flagged = [f'{s["id"]}: {", ".join(s["flags"])}' for s in sources if s.get("flags")]
    results.append(gate("source safety", "warn" if flagged else "pass",
                        ("instruction-like text found in " + "; ".join(flagged)) if flagged else "no instruction-like text in sources"))

    if check_urls:
        urls = [s["url"] for s in sources if s.get("url") and s["id"] in cites]
        bad = check_links(urls) if urls else []
        results.append(gate("links", "warn" if bad else "pass", ("unreachable: " + ", ".join(f"{u} ({why})" for u, why in bad)) if bad else f"{len(urls)} cited link(s) reachable"))
    return results


def has_blocking(gates: list[dict]) -> bool:
    return any(g["status"] == "fail" for g in gates)

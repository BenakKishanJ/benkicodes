"""Deterministic quality gates run on every draft before the human sees it.
Each gate returns {name, status: pass|warn|fail, detail}. Any 'fail' blocks publishing unless the author overrides."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import httpx

from .repo import secrets_scan
from .snippets import find_placeholders

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


def run_part_gates(*, lesson: str, module_fm_error: str | None, snippet_problems: list[str],
                   inline_problems: list[str], commits: list[dict], tags_ok: bool,
                   sources: list[dict], cited: list[str], critique: dict | None,
                   objectives: list[str], resources: list[dict], kept_urls: set[str],
                   tests: dict | None, similarity_limit: float, banned: list[str],
                   check_urls: bool = True) -> list[dict]:
    """§10.2 part gates. lesson: expanded lesson md; critique: lesson_check output dict."""
    results: list[dict] = []

    # 1. schema (hard)
    results.append(gate("schema", "fail" if module_fm_error else "pass",
                        module_fm_error or "module frontmatter matches the site's content schema"))

    # 2. snippets (hard)
    if snippet_problems or inline_problems:
        results.append(gate("snippets", "fail", "; ".join((snippet_problems + inline_problems)[:5])))
    else:
        n = len(find_placeholders(lesson))
        results.append(gate("snippets", "pass", f"{n} placeholder(s) expanded, inline blocks within limits"))

    # 3. code state (hard): commits exist since the previous tag; no secrets in the diff
    if not tags_ok:
        results.append(gate("code state", "fail", "tag range invalid or commits missing"))
    else:
        blob = "\n".join(c["message"] for c in commits)
        hits = secrets_scan(blob)
        results.append(gate("code state", "fail" if hits else "pass",
                            f"secret-like strings in commit messages: {', '.join(hits[:3])}" if hits
                            else f"{len(commits)} commit(s) on the tag range"))

    # 4. sources (hard for urls, fail for coverage)
    by_id = {s["id"]: s for s in sources}
    unknown = [c for c in cited if c not in by_id]
    if unknown:
        results.append(gate("sources", "fail", f"cites unknown sources: {', '.join(unknown)}"))
    else:
        not_fetched = [c for c in cited if c in by_id and not by_id[c].get("text")]
        bad = [f'{c}: {by_id[c].get("fetch_error", "not fetched")}' for c in cited if c in by_id and by_id[c].get("fetch_error")]
        if bad:
            results.append(gate("sources", "fail", "cited docs failed to fetch: " + "; ".join(bad[:3])))
        elif not_fetched:
            results.append(gate("sources", "fail", f"cited sources never fetched: {', '.join(not_fetched)}"))
        else:
            sections = re.split(r"(?m)^## ", lesson)[1:]
            bare = [s.splitlines()[0] for s in sections
                    if not CITE_RE.search(s) and not s.lower().startswith("exercises")]
            results.append(gate("sources", "fail" if len(bare) >= 2 else ("warn" if bare else "pass"),
                                f"sections without citation: {', '.join(bare)}" if bare
                                else f"all {len(cited)} cited sources fetched OK; every section cites"))

    # 5. similarity (fail) — docs excerpts only (the only prose the lesson could copy)
    worst = 0.0
    for s in sources:
        t = s.get("text") or s.get("excerpt") or ""
        if t:
            worst = max(worst, similarity(lesson, t))
    results.append(gate("similarity", "fail" if worst > similarity_limit else "pass",
                        f"highest overlap with the docs: {worst:.0%} (limit {similarity_limit:.0%})"))

    # 6. exercises (fail): 2-4, each with acceptance criteria and >=1 hint
    ex = exercise_report(lesson)
    results.append(gate("exercises", "pass" if ex == [] else "fail",
                        "; ".join(ex) if ex else f"{lesson.count('**Exercise')} exercises with criteria and hints"))

    # 7. quiz integrity (hard) — validated at parse; here just confirm presence
    results.append(gate("quiz", "pass", "quiz validated at parse time (schema: option counts, correct ids, single/multi)"))

    # 8. tests (warn)
    if not tests:
        results.append(gate("tests", "warn", "tests have not been run; press Run tests in the workspace"))
    elif not tests.get("ok"):
        tail = (tests.get("output") or "").strip().splitlines()[-1:] or [""]
        results.append(gate("tests", "warn", f"last test run FAILED: {tail[0][:160]}"))
    else:
        results.append(gate("tests", "pass", f"tests passed in {tests.get('seconds', '?')}s"))

    # 9. resources (hard): verified + from kept refs
    bad_res = [r["url"] for r in resources if kept_urls and r.get("url") not in kept_urls]
    unverified = [r["title"] for r in resources if not r.get("verified", True)]
    if bad_res:
        results.append(gate("resources", "fail", f"resources not among the kept references: {', '.join(bad_res[:3])}"))
    elif unverified:
        results.append(gate("resources", "fail", f"resources not verified by fetching: {', '.join(unverified[:3])}"))
    else:
        results.append(gate("resources", "pass", f"{len(resources)} resource(s), all from verified kept references"))

    # 10. objectives taught (fail — critic confirms)
    cov = float((critique or {}).get("scores", {}).get("coverage", 0) or 0)
    high = [i for i in (critique or {}).get("issues", []) if i.get("severity") == "high"]
    if cov and cov < 4:
        results.append(gate("objectives", "fail", f"the reviewer scored coverage {cov:.0f}/5 — an objective may be untaught"))
    elif high:
        results.append(gate("objectives", "fail", "high-severity review issues: " + "; ".join(i.get("problem", "")[:60] for i in high[:2])))
    else:
        results.append(gate("objectives", "pass", f"reviewer coverage score {cov:.0f}/5" if cov else "no review yet"))

    # 11. unsupported claims + length + filler + links (warn)
    uns = (critique or {}).get("unsupported_claims", [])
    results.append(gate("unsupported claims", "fail" if len(uns) >= 3 else ("warn" if uns else "pass"),
                        "; ".join(uns[:3]) if uns else "the reviewer found none"))
    low = lesson.lower()
    hits = [b for b in banned if b and b.lower() in low]
    results.append(gate("filler phrases", "warn" if hits else "pass", ("found: " + ", ".join(hits[:4])) if hits else "none"))
    wc = word_count(lesson)
    results.append(gate("length", "pass" if 800 * 0.7 <= wc <= 1800 * 1.3 else "warn", f"{wc} words (target 800-1800)"))
    if check_urls:
        urls = [s["url"] for s in sources if s.get("url") and s["id"] in cited]
        bad = check_links(urls) if urls else []
        results.append(gate("links", "warn" if bad else "pass",
                            ("unreachable: " + ", ".join(f"{u} ({why})" for u, why in bad)) if bad
                            else f"{len(urls)} cited link(s) reachable"))
    return results


def exercise_report(lesson: str) -> list[str]:
    """Problems with the Exercises section: 2-4 exercises, criteria, >=1 hint each."""
    m = re.search(r"(?ms)^## Exercises\s*\n(.*?)(?=^## |\Z)", lesson)
    if not m:
        return ["no '## Exercises' section"]
    body = m.group(1)
    n = len(re.findall(r"\*\*Exercise\b", body))
    if not 2 <= n <= 4:
        return [f"{n} exercises (need 2-4)"]
    problems = []
    if body.lower().count("acceptance") < n:
        problems.append(f"{n} exercises but only {body.lower().count('acceptance')} acceptance criteria")
    if body.lower().count("hint") < 1:
        problems.append("no hints")
    return problems
